from __future__ import annotations

import json
from html import escape
from pathlib import Path


def _report_path() -> Path:
    candidates = [
        Path.cwd() / "reports" / "performance_comparison.json",
        Path(__file__).resolve().parents[2] / "reports" / "performance_comparison.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Run: .\\.venv\\Scripts\\python.exe benchmarks\\comparison.py")


def comparison_report_html() -> str:
    data = json.loads(_report_path().read_text(encoding="utf-8"))
    metadata = data["metadata"]
    rows = []
    for item in data["measurements"]:
        paths = f"{item['paths']:,}" if item["paths"] else "Formula"
        standard_error = "N/A" if item["standard_error"] is None else f"{item['standard_error']:.6f}"
        interval = (
            "Exact formula" if item["ci95_low"] is None
            else f"{item['ci95_low']:.6f} – {item['ci95_high']:.6f}"
        )
        z_score = "N/A" if item["combined_error_z"] is None else f"{item['combined_error_z']:.2f}"
        coverage = (
            "N/A" if item["reference_in_ci95"] is None
            else ("Yes" if item["reference_in_ci95"] else "No")
        )
        rows.append(f"""<tr>
<td><b>{escape(item['method'])}</b></td><td>{paths}</td><td>{item['price']:.6f}</td>
<td class="time">{item['elapsed_ms']:.4f}</td><td>{item['time_vs_black76_x']:,.0f}×</td>
<td>{standard_error}</td><td>{interval}</td><td>{item['absolute_error']:.6f}</td>
<td>{item['relative_error_pct']:.3f}%</td><td>{z_score}</td><td>{coverage}</td>
<td>{item['estimated_peak_mb']:.2f}</td></tr>""")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pricing Performance and Accuracy Report</title><style>
body{{margin:0;background:#07111f;color:#e8f1fb;font:14px system-ui,Segoe UI,sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px}}h1{{margin-bottom:5px}}h2{{margin-top:28px;color:#c6dcf3}}
a{{color:#22d3ee}}.sub,.note{{color:#96abc3}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}}
.card,.section{{background:#101d2f;border:1px solid #263b55;border-radius:11px;padding:17px}}.card b{{font-size:22px;color:#4ade80;display:block;margin-top:5px}}
.table-wrap{{overflow:auto;background:#101d2f;border:1px solid #263b55;border-radius:11px}}table{{border-collapse:collapse;width:100%;min-width:1200px}}
th,td{{padding:10px;text-align:right;border-bottom:1px solid #263b55;white-space:nowrap}}th{{color:#9fb8d3;background:#0b1728;position:sticky;top:0}}th:first-child,td:first-child{{text-align:left}}.time{{color:#22d3ee;font-weight:700}}
li{{margin:8px 0;line-height:1.5}}code{{color:#fbbf24}}@media(max-width:800px){{.cards{{grid-template-columns:1fr}}}}
</style></head><body><main><a href="/">← Pricing dashboard</a>
<h1>Time Consumption and Accuracy Comparison</h1>
<div class="sub">Measured {escape(metadata['generated_at'])} · Python {escape(metadata['python'])} · {metadata['logical_cpus']} logical CPUs</div>
<div class="cards"><div class="card">Black-76 latency<b>{data['measurements'][0]['elapsed_ms']:.4f} ms</b></div>
<div class="card">Asian GBM reference<b>{metadata['gbm_reference']['price']:.6f}</b><span>500,000 paths</span></div>
<div class="card">Asian OU reference<b>{metadata['ou_reference']['price']:.6f}</b><span>500,000 paths</span></div></div>
<h2>Measured results</h2><div class="table-wrap"><table><thead><tr><th>Method</th><th>Paths</th><th>Price</th><th>Time ms</th><th>Time vs Black-76</th><th>Std. error</th><th>Approx. 95% CI</th><th>Absolute error</th><th>Relative error</th><th>Combined error z</th><th>Reference in CI</th><th>Peak MB</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class="section"><h2>How to interpret this report</h2><ul>
<li><b>Black-76</b> is a closed-form European futures-option price. It has no Monte Carlo sampling error and is the live low-latency path.</li>
<li><b>Asian GBM and Asian OU</b> price arithmetic-average options. Each is compared only with an independent 500,000-path reference from the same model.</li>
<li>Black-76 is not an accuracy reference for Asian options because the payoff is different.</li>
<li>Standard error measures numerical sampling uncertainty, not model or market-calibration risk. Approximately four times as many paths are needed to halve it.</li>
<li>A combined error z-score below about 1.96 is statistically consistent with the independent reference at the conventional 95% level.</li>
<li>Regenerate measurements on this computer with <code>.\\.venv\\Scripts\\python.exe benchmarks\\comparison.py</code>, then refresh this page.</li>
</ul></div><p class="note">Inputs: futures 78, strike 80, maturity 0.5 years, rate 4%, volatility 32%, 64 monitoring steps.</p>
</main></body></html>"""
