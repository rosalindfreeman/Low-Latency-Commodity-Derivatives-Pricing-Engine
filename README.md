# Low-Latency Commodity Derivatives Pricing Engine

A production-shaped Python project for pricing commodity futures options. It combines a
millisecond-oriented Black-76 path with a slower, cached Monte Carlo path for Asian options.
The included simulated feed covers gold (`GC`), silver (`SI`), crude oil (`CL`) and natural
gas (`NG`).

## Architecture

```text
async feed ──> copy-on-write in-memory market state ──> FastAPI / WebSocket
                              │                              │
                              └── volatility surface ───────┤
                                                             ├─ Black-76 + analytical Greeks
                                                             └─ chunked NumPy Monte Carlo
                                                                └─ process pool + TTL cache
```

The fast lane uses Black-76 analytical pricing and Greeks. The slow lane prices arithmetic
Asian options under GBM or mean-reverting Ornstein-Uhlenbeck dynamics. Monte Carlo arrays are
allocated one chunk at a time, bounding peak memory at approximately
`chunk_size × steps × 8` bytes for GBM. Independent scenario jobs can run in a process pool.

## Features

- Black-76 calls and puts with delta, gamma, vega, theta and rho
- Chunked, vectorised arithmetic-Asian Monte Carlo with a standard error
- Exact-discretised OU commodity model: `dX = κ(θ-X)dt + σdW`
- Bilinear strike/maturity volatility-surface interpolation
- Async simulated market ingestion and a POST endpoint for external ticks
- Immutable in-memory snapshots and version-aware TTL pricing cache
- FastAPI REST and streaming WebSocket interfaces
- Multiprocessing for Monte Carlo and scenario grids
- Per-request latency measurement, tests, Docker and Compose

## Run locally

Python 3.11+ is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn commodity_engine.api:app --reload
```

On Windows PowerShell, the complete recommended setup is:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn commodity_engine.api:app --host 127.0.0.1 --port 8000
```

Use the `.venv` Python for every command. Installing a package into one Python installation
does not make it available to another Python installation. Direct file execution is also
supported after installation:

```powershell
.\.venv\Scripts\python.exe src\commodity_engine\main.py
```

Open `http://localhost:8000/docs`. Seeded symbols are `GC`, `SI`, `CL`, and `NG`.

Open `http://localhost:8000/` for the interactive pricing simulation dashboard. It displays
the simulated live market, lets you run Black-76, Asian GBM, or mean-reverting Asian OU prices,
and shows price, latency, volatility, Monte Carlo error, Greeks, and result history.

Open `http://localhost:8000/report/comparison` to view the measured time-consumption and
accuracy comparison in the running application.

Running `src\\commodity_engine\\main.py` automatically opens
`http://127.0.0.1:8000/full-report`, which combines the interactive pricing simulation and
the measured time/accuracy comparison in two tabs. Set `ENGINE_OPEN_BROWSER=0` to disable
automatic browser opening or `ENGINE_PORT=8001` to use another port.

### Live latency report

Open `http://localhost:8000/report/latency` after starting the API. The report contains a live
time counter, total request counts, and rolling minimum, average, p50, p95, p99, maximum and
latest latency in milliseconds. It reports `black76_fast_path`, `monte_carlo_slow_path`, and
`cache_hit` separately so the low-latency route is not hidden by expensive simulations.

The same data is available as JSON from `GET /metrics/latency`. Generate observations with a
few `/price` requests or run `python benchmarks/latency.py` against the in-process engine.

## API examples

Fast Black-76 price with volatility-surface lookup:

```bash
curl -X POST http://localhost:8000/price \
  -H "Content-Type: application/json" \
  -d '{"symbol":"CL","strike":80,"maturity":0.5,"option_type":"call"}'
```

Chunked Asian option using mean reversion:

```bash
curl -X POST http://localhost:8000/price \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NG","strike":3.2,"maturity":1,"option_type":"call", \
       "model":"asian_ou","paths":200000,"steps":96,"chunk_size":25000, \
       "kappa":2.5,"theta":3.0}'
```

Scenario grid:

```bash
curl -X POST http://localhost:8000/scenarios \
  -H "Content-Type: application/json" \
  -d '{"base":{"symbol":"GC","strike":2400,"maturity":0.5}, \
       "spot_shocks":[-0.05,0,0.05],"volatility_shocks":[-0.02,0,0.02]}'
```

WebSocket clients connect to `ws://localhost:8000/ws/prices` and send one subscription:

```json
{"symbol":"CL","strike":80,"maturity":0.5,"option_type":"call","interval_ms":250}
```

## Docker

```bash
docker compose up --build
```

## Verification and benchmark

```bash
pytest -q
python scripts/smoke_test.py
python benchmarks/latency.py
python benchmarks/comparison.py
```

Latency varies by machine. The benchmark reports Black-76 warm-cache percentiles and a Monte
Carlo measurement separately; these workloads should not be presented as comparable SLAs.
`benchmarks/comparison.py` produces a complete measured time/accuracy report, CSV, and JSON in
`reports/`, including Monte Carlo convergence against independent high-path reference runs.

## Integration notes

`simulated_feed()` is an adapter boundary. Replace it with an async vendor client that yields
`MarketTick` objects; network waits across instruments should be scheduled concurrently. A
database belongs off the request path: persist ticks and results asynchronously, while pricing
continues to read the latest in-memory snapshot. For a multi-host deployment, feed each replica
from the same ordered stream and include source sequence numbers in ticks.

This project is an engineering example, not investment advice or a validated trading model.
