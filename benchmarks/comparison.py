from __future__ import annotations

import argparse
import csv
import json
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from commodity_engine.black76 import price as black76_price
from commodity_engine.monte_carlo import MonteCarloResult, asian_gbm, asian_ou


@dataclass(slots=True)
class Measurement:
    method: str
    paths: int | None
    steps: int | None
    price: float
    elapsed_ms: float
    standard_error: float | None
    ci95_low: float | None
    ci95_high: float | None
    reference_price: float
    absolute_error: float
    relative_error_pct: float
    throughput_paths_sec: float | None
    estimated_peak_mb: float
    time_vs_black76_x: float | None
    reference_in_ci95: bool | None
    combined_error_z: float | None


def timed(callable_, repeats: int = 1):
    durations = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter_ns()
        result = callable_()
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
    return result, statistics.median(durations)


def mc_measurement(method: str, paths: int, steps: int,
                   reference: MonteCarloResult) -> Measurement:
    if method == "Asian GBM":
        function = lambda: asian_gbm(
            78.0, 80.0, 0.5, 0.04, 0.32, paths=paths, steps=steps,
            chunk_size=min(paths, 25_000), seed=42,
        )
        # GBM stores one paths × steps float64 normal/path matrix per chunk.
        peak = min(paths, 25_000) * steps * 8 / 1024**2
    else:
        function = lambda: asian_ou(
            78.0, 80.0, 0.5, 0.04, 0.32 * 78.0, kappa=2.5, theta=75.0,
            paths=paths, steps=steps, chunk_size=min(paths, 25_000), seed=42,
        )
        # OU only retains a few one-dimensional arrays because it advances step by step.
        peak = min(paths, 25_000) * 8 * 4 / 1024**2
    result, elapsed = timed(function)
    assert isinstance(result, MonteCarloResult)
    error = abs(result.price - reference.price)
    relative = error / reference.price * 100 if reference.price else 0.0
    ci_low = result.price - 1.96 * result.standard_error
    ci_high = result.price + 1.96 * result.standard_error
    combined_se = math.sqrt(result.standard_error**2 + reference.standard_error**2)
    return Measurement(
        method=method, paths=paths, steps=steps, price=result.price, elapsed_ms=elapsed,
        standard_error=result.standard_error,
        ci95_low=ci_low, ci95_high=ci_high,
        reference_price=reference.price, absolute_error=error, relative_error_pct=relative,
        throughput_paths_sec=paths / (elapsed / 1000), estimated_peak_mb=peak,
        time_vs_black76_x=None, reference_in_ci95=ci_low <= reference.price <= ci_high,
        combined_error_z=error / combined_se,
    )


def run_benchmark(reference_paths: int = 500_000) -> tuple[list[Measurement], dict]:
    inputs = {"futures": 78.0, "strike": 80.0, "maturity": 0.5, "rate": 0.04,
              "relative_volatility": 0.32, "steps": 64, "seed": 42}
    gbm_reference = asian_gbm(
        78, 80, 0.5, 0.04, 0.32, paths=reference_paths, steps=64,
        chunk_size=25_000, seed=2026,
    )
    ou_reference = asian_ou(
        78, 80, 0.5, 0.04, 0.32 * 78, kappa=2.5, theta=75,
        paths=reference_paths, steps=64, chunk_size=25_000, seed=2026,
    )

    analytical = black76_price(78, 80, 0.5, 0.04, 0.32)
    _, total_ms = timed(lambda: [black76_price(78, 80, 0.5, 0.04, 0.32) for _ in range(20_000)], 5)
    black_per_call = total_ms / 20_000
    measurements = [Measurement(
        method="Black-76", paths=None, steps=None, price=analytical,
        elapsed_ms=black_per_call, standard_error=None, ci95_low=None, ci95_high=None,
        reference_price=analytical, absolute_error=0.0, relative_error_pct=0.0,
        throughput_paths_sec=None, estimated_peak_mb=0.0,
        time_vs_black76_x=1.0, reference_in_ci95=None, combined_error_z=None,
    )]
    for paths in (5_000, 25_000, 100_000):
        measurements.append(mc_measurement("Asian GBM", paths, 64, gbm_reference))
    for paths in (5_000, 25_000, 100_000):
        measurements.append(mc_measurement("Asian OU", paths, 64, ou_reference))
    for item in measurements[1:]:
        item.time_vs_black76_x = item.elapsed_ms / black_per_call
    metadata = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "logical_cpus": os.cpu_count(), "inputs": inputs, "reference_paths": reference_paths,
        "gbm_reference": asdict(gbm_reference), "ou_reference": asdict(ou_reference),
    }
    return measurements, metadata


def markdown(measurements: list[Measurement], metadata: dict) -> str:
    rows = []
    for x in measurements:
        ci = "Exact formula" if x.ci95_low is None else f"[{x.ci95_low:.6f}, {x.ci95_high:.6f}]"
        rows.append(
            f"| {x.method} | {x.paths or 'N/A'} | {x.price:.6f} | {x.elapsed_ms:.4f} | "
            f"{x.standard_error if x.standard_error is not None else 0:.6f} | {ci} | "
            f"{x.absolute_error:.6f} | {x.relative_error_pct:.3f}% | "
            f"{x.time_vs_black76_x:,.0f}x | "
            f"{'N/A' if x.combined_error_z is None else f'{x.combined_error_z:.2f}'} | "
            f"{'N/A' if x.reference_in_ci95 is None else x.reference_in_ci95} | "
            f"{x.estimated_peak_mb:.2f} |"
        )
    return f"""# Pricing Method Time and Accuracy Comparison

Generated: {metadata['generated_at']}  
Runtime: Python {metadata['python']} on {metadata['platform']} ({metadata['logical_cpus']} logical CPUs)

## Executive summary

Black-76 is the low-latency method: it uses a closed-form formula and has no sampling error.
Monte Carlo is intentionally slower but supports arithmetic-average Asian payoffs and
mean-reverting dynamics. Increasing paths generally reduces Monte Carlo standard error at the
theoretical rate of approximately `1/sqrt(paths)`, while runtime grows approximately linearly.

The Black-76 price must **not** be treated as the accuracy reference for the Asian prices: it
prices a European futures option with a different payoff. Asian GBM rows are compared with a
{metadata['reference_paths']:,}-path Asian GBM reference; Asian OU rows use a separate
{metadata['reference_paths']:,}-path Asian OU reference. This is a numerical-convergence study,
not proof that a model matches observed market prices.

## Test contract and assumptions

- Futures level: 78.00; strike: 80.00; maturity: 0.50 years; rate: 4.00%
- Relative volatility: 32.00%; 64 monitoring steps; deterministic seed 42
- OU parameters: kappa 2.5, theta 75.0, absolute sigma 24.96
- Monte Carlo references use seed 2026 to avoid comparing a sample with itself
- Timings are wall-clock engine computation, excluding HTTP/network and UI rendering
- Black-76 time is the median of five 20,000-price batches divided by 20,000
- Peak memory is an implementation estimate for dominant numerical arrays, not process RSS

## Measured results

| Method | Paths | Price | Time (ms) | Std. error | Approx. 95% CI | Abs. error vs same-model reference | Relative error | Time vs Black-76 | Combined error z | Reference in sample CI | Est. peak MB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

Reference values: Asian GBM **{metadata['gbm_reference']['price']:.6f}**
(SE {metadata['gbm_reference']['standard_error']:.6f}); Asian OU
**{metadata['ou_reference']['price']:.6f}**
(SE {metadata['ou_reference']['standard_error']:.6f}).

## Interpretation

1. **Latency:** Black-76 is suitable for synchronous quote updates because its workload is
   constant and tiny. Cache hits can be faster at service level when they avoid recomputation.
2. **Accuracy:** Monte Carlo standard error measures sampling uncertainty, not model risk. A
   narrower confidence interval means more numerical precision, but not necessarily a better
   market model. A combined error z-score below about 1.96 is statistically consistent with the
   independent reference at the conventional 95% level.
3. **Path count trade-off:** Roughly 4× more paths are required to halve standard error. Select
   paths using an explicit error tolerance rather than an arbitrary large number.
4. **Mean reversion:** OU and GBM prices differ because their dynamics differ. OU is relevant
   for energy-style levels but can allow negative simulated prices; production power/gas work
   may require shifted, lognormal mean-reverting, or multi-factor models.
5. **Reproducibility:** OS scheduling, CPU power management, Python/NumPy versions, and other
   processes affect timings. Run several times on the deployment host before setting an SLA.

## Recommended two-speed policy

- Use Black-76 plus analytical Greeks for every live tick and trader request.
- Return the last cached Asian result immediately, tagged with its market-state version.
- Reprice Asian books asynchronously only after a meaningful market move or cache invalidation.
- Use Monte Carlo standard error and market-version age as report fields.
- Benchmark p50/p95/p99 API latency under concurrent load separately from these single-process
  numerical timings.

## Reproduce

```powershell
.\\.venv\\Scripts\\python.exe benchmarks\\comparison.py
```

The command rewrites this Markdown report plus `performance_comparison.csv` and
`performance_comparison.json` in the `reports` directory.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare pricing time and numerical accuracy")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--reference-paths", type=int, default=500_000)
    args = parser.parse_args()
    measurements, metadata = run_benchmark(args.reference_paths)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = [asdict(item) for item in measurements]
    (output / "performance_comparison.json").write_text(
        json.dumps({"metadata": metadata, "measurements": records}, indent=2), encoding="utf-8"
    )
    with (output / "performance_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)
    (output / "performance_report.md").write_text(
        markdown(measurements, metadata), encoding="utf-8"
    )
    print(output / "performance_report.md")


if __name__ == "__main__":
    main()
