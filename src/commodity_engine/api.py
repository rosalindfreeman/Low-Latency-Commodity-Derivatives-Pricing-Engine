from __future__ import annotations

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from commodity_engine.dashboard import DASHBOARD_HTML
from commodity_engine.engine import PricingEngine
from commodity_engine.market import MarketState, consume_feed, seed_market_state, simulated_feed
from commodity_engine.models import (
    HealthResponse,
    MarketTick,
    PriceRequest,
    PriceResponse,
    ScenarioRequest,
    ScenarioResult,
    Subscription,
)
from commodity_engine.report_view import comparison_report_html

market_state = MarketState()
engine = PricingEngine(market_state)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await seed_market_state(market_state)
    interval = float(os.getenv("MARKET_TICK_INTERVAL", "0.25"))
    feed_task = asyncio.create_task(consume_feed(market_state, simulated_feed(interval)))
    yield
    feed_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await feed_task
    engine.close()


app = FastAPI(
    title="Low-Latency Commodity Derivatives Pricing Engine",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    """Interactive browser interface for pricing simulations."""
    return DASHBOARD_HTML


@app.get("/full-report", response_class=HTMLResponse, include_in_schema=False)
async def full_report() -> str:
    """One browser page containing the interactive simulation and measured report."""
    return """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Complete Commodity Pricing Report</title><style>
body{margin:0;background:#07111f;color:#e8f1fb;font:14px system-ui,Segoe UI,sans-serif}
header{position:sticky;top:0;z-index:5;background:#0b1728;border-bottom:1px solid #263b55;padding:14px 22px;display:flex;align-items:center;justify-content:space-between}
h1{font-size:19px;margin:0}.tabs button{border:1px solid #38516d;background:#101d2f;color:#e8f1fb;border-radius:7px;padding:9px 14px;margin-left:7px;cursor:pointer}.tabs button.active{background:#0e7490}.view{display:none;width:100%;height:calc(100vh - 63px);border:0}.view.active{display:block}
</style></head><body><header><h1>Complete Pricing Simulation & Performance Report</h1>
<div class="tabs"><button id="simulationButton" class="active" onclick="show('simulation')">1. Pricing Simulation</button><button id="comparisonButton" onclick="show('comparison')">2. Time & Accuracy Comparison</button></div></header>
<iframe id="simulation" class="view active" src="/"></iframe>
<iframe id="comparison" class="view" src="/report/comparison"></iframe>
<script>function show(name){for(const e of document.querySelectorAll('.view,.tabs button'))e.classList.remove('active');document.getElementById(name).classList.add('active');document.getElementById(name+'Button').classList.add('active')}</script>
</body></html>"""


@app.get("/report/comparison", response_class=HTMLResponse, include_in_schema=False)
async def comparison_report() -> str:
    """Measured method timing, convergence, and accuracy comparison."""
    try:
        return comparison_report_html()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(instruments=len(market_state.all()), cache_entries=len(engine.cache))


@app.get("/market")
async def markets() -> list[dict]:
    return [
        {"symbol": x.symbol, "futures_price": x.futures_price, "rate": x.rate,
         "volatility": x.volatility, "version": x.version, "timestamp_ns": x.timestamp_ns}
        for x in market_state.all().values()
    ]


@app.get("/metrics/latency")
async def latency_metrics() -> dict:
    """Machine-readable rolling timing report, measured in milliseconds."""
    return {
        "unit": "milliseconds",
        "sample_window": 10_000,
        "categories": {
            name: asdict(summary)
            for name, summary in engine.latencies.report().items()
        },
    }


@app.get("/report/latency", response_class=HTMLResponse)
async def latency_report() -> str:
    """Human-readable report with a live elapsed-time counter and rolling percentiles."""
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>Pricing Latency Report</title>
<style>
body{font-family:system-ui;margin:2rem;background:#0b1220;color:#e5eefc}h1{margin-bottom:.25rem}
.clock{font-size:2rem;color:#67e8f9;margin:1rem 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}
.card{background:#172033;border:1px solid #334155;border-radius:12px;padding:1rem}.value{font-size:1.5rem;color:#86efac}
table{width:100%;border-collapse:collapse}td{padding:.3rem;border-bottom:1px solid #334155}td:last-child{text-align:right}
.note{color:#94a3b8}button{padding:.6rem 1rem;border-radius:8px;border:0;cursor:pointer}
</style></head><body><h1>Low-Latency Pricing Report</h1>
<div class="note">Rolling window: latest 10,000 observations per category</div>
<div class="clock">Report running time: <span id="clock">00:00:00.000</span></div>
<div id="cards" class="cards"></div><p class="note">Updates every second. All timings are end-to-end engine milliseconds.</p>
<script>
const started=performance.now();
function clock(){const t=performance.now()-started,h=Math.floor(t/3600000),m=Math.floor(t/60000)%60,s=Math.floor(t/1000)%60,ms=Math.floor(t%1000);document.querySelector('#clock').textContent=[h,m,s].map(x=>String(x).padStart(2,'0')).join(':')+'.'+String(ms).padStart(3,'0')}
async function refresh(){const r=await fetch('/metrics/latency'),d=await r.json(),root=document.querySelector('#cards');root.innerHTML='';for(const [name,x] of Object.entries(d.categories)){const card=document.createElement('div');card.className='card';card.innerHTML=`<h2>${name.replaceAll('_',' ')}</h2><div class="value">Latest: ${x.latest_ms.toFixed(4)} ms</div><table><tr><td>Request count</td><td>${x.count}</td></tr><tr><td>Minimum</td><td>${x.minimum_ms.toFixed(4)} ms</td></tr><tr><td>Average</td><td>${x.average_ms.toFixed(4)} ms</td></tr><tr><td>p50</td><td>${x.p50_ms.toFixed(4)} ms</td></tr><tr><td>p95</td><td>${x.p95_ms.toFixed(4)} ms</td></tr><tr><td>p99</td><td>${x.p99_ms.toFixed(4)} ms</td></tr><tr><td>Maximum</td><td>${x.maximum_ms.toFixed(4)} ms</td></tr></table>`;root.appendChild(card)}if(!root.children.length)root.innerHTML='<div class="card">Send pricing requests to populate the report.</div>'}
setInterval(clock,31);setInterval(refresh,1000);refresh();
</script></body></html>"""


@app.post("/market/tick")
async def publish_tick(tick: MarketTick) -> dict:
    snapshot = await market_state.update(tick)
    return {"symbol": snapshot.symbol, "version": snapshot.version}


@app.post("/price", response_model=PriceResponse)
async def calculate_price(request: PriceRequest) -> PriceResponse:
    try:
        return await engine.price(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/scenarios", response_model=list[ScenarioResult])
async def calculate_scenarios(request: ScenarioRequest) -> list[ScenarioResult]:
    try:
        return await engine.scenarios(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.websocket("/ws/prices")
async def stream_prices(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        subscription = Subscription.model_validate(await websocket.receive_json())
        version = -1
        while True:
            snapshot = await market_state.wait_for_change(
                subscription.symbol, version, subscription.interval_ms / 1000
            )
            version = snapshot.version
            request = PriceRequest(
                symbol=subscription.symbol, strike=subscription.strike,
                maturity=subscription.maturity, option_type=subscription.option_type,
                use_surface=subscription.use_surface,
            )
            result = await engine.price(request)
            await websocket.send_json(result.model_dump(mode="json"))
    except (WebSocketDisconnect, KeyError):
        return
