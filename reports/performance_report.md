# Pricing Method Time and Accuracy Comparison

Generated: 2026-08-13 16:40:42 GMT Daylight Time  
Runtime: Python 3.12.10 on Windows-11-10.0.26200-SP0 (14 logical CPUs)

## Executive summary

Black-76 is the low-latency method: it uses a closed-form formula and has no sampling error.
Monte Carlo is intentionally slower but supports arithmetic-average Asian payoffs and
mean-reverting dynamics. Increasing paths generally reduces Monte Carlo standard error at the
theoretical rate of approximately `1/sqrt(paths)`, while runtime grows approximately linearly.

The Black-76 price must **not** be treated as the accuracy reference for the Asian prices: it
prices a European futures option with a different payoff. Asian GBM rows are compared with a
500,000-path Asian GBM reference; Asian OU rows use a separate
500,000-path Asian OU reference. This is a numerical-convergence study,
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
| Black-76 | N/A | 6.038492 | 0.0008 | 0.000000 | Exact formula | 0.000000 | 0.000% | 1x | N/A | N/A | 0.00 |
| Asian GBM | 5000 | 3.091943 | 7.2084 | 0.081208 | [2.932775, 3.251111] | 0.034759 | 1.112% | 9,223x | 0.43 | True | 2.44 |
| Asian GBM | 25000 | 3.100814 | 36.2459 | 0.036215 | [3.029832, 3.171796] | 0.025888 | 0.828% | 46,378x | 0.70 | True | 12.21 |
| Asian GBM | 100000 | 3.120672 | 138.5260 | 0.018106 | [3.085185, 3.156159] | 0.006030 | 0.193% | 177,250x | 0.30 | True | 12.21 |
| Asian OU | 5000 | 1.308557 | 3.1871 | 0.038889 | [1.232334, 1.384779] | 0.010748 | 0.828% | 4,078x | 0.28 | True | 0.15 |
| Asian OU | 25000 | 1.305796 | 16.6315 | 0.016989 | [1.272497, 1.339096] | 0.007988 | 0.615% | 21,281x | 0.46 | True | 0.76 |
| Asian OU | 100000 | 1.317664 | 58.8819 | 0.008596 | [1.300815, 1.334512] | 0.019855 | 1.530% | 75,342x | 2.11 | False | 0.76 |

Reference values: Asian GBM **3.126702**
(SE 0.008110); Asian OU
**1.297809**
(SE 0.003817).

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
.\.venv\Scripts\python.exe benchmarks\comparison.py
```

The command rewrites this Markdown report plus `performance_comparison.csv` and
`performance_comparison.json` in the `reports` directory.
