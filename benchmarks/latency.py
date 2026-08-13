from __future__ import annotations

import asyncio
import statistics
import time

import numpy as np

from commodity_engine.engine import PricingEngine
from commodity_engine.market import MarketState, seed_market_state
from commodity_engine.models import ModelType, PriceRequest


async def main() -> None:
    state = MarketState()
    await seed_market_state(state)
    engine = PricingEngine(state, workers=1)
    request = PriceRequest(symbol="CL", strike=80, maturity=0.5)
    await engine.price(request)
    samples = []
    for _ in range(2_000):
        started = time.perf_counter_ns()
        await engine.price(request)
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    print(f"Black-76 cached median={statistics.median(samples):.4f} ms "
          f"p95={np.percentile(samples, 95):.4f} ms p99={np.percentile(samples, 99):.4f} ms")

    mc = PriceRequest(symbol="CL", strike=80, maturity=0.5, model=ModelType.ASIAN_GBM,
                      paths=100_000, steps=64, chunk_size=25_000, run_in_process=False)
    result = await engine.price(mc)
    print(f"Asian GBM price={result.price:.4f} se={result.standard_error:.4f} "
          f"latency={result.latency_ms:.2f} ms")
    engine.close()


if __name__ == "__main__":
    asyncio.run(main())

