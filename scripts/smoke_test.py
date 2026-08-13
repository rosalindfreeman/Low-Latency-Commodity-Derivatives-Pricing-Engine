"""Small verification harness that only needs runtime dependencies, not pytest."""

import asyncio
import math

import numpy as np

from commodity_engine.black76 import price
from commodity_engine.engine import PricingEngine
from commodity_engine.market import MarketState, seed_market_state
from commodity_engine.models import MarketTick, PriceRequest
from commodity_engine.monte_carlo import asian_gbm
from commodity_engine.vol_surface import VolatilitySurface


async def main() -> None:
    call = price(100, 95, 0.75, 0.04, 0.3, "call")
    put = price(100, 95, 0.75, 0.04, 0.3, "put")
    assert abs((call - put) - math.exp(-0.03) * 5) < 1e-10

    whole = asian_gbm(100, 100, 1, 0.03, 0.2, paths=10_000, steps=24,
                      chunk_size=10_000, seed=12)
    chunked = asian_gbm(100, 100, 1, 0.03, 0.2, paths=10_000, steps=24,
                        chunk_size=1_000, seed=12)
    assert abs(whole.price - chunked.price) < 1e-12

    surface = VolatilitySurface(
        np.array([1.0, 2.0]), np.array([90.0, 110.0]), np.array([[0.2, 0.3], [0.3, 0.4]])
    )
    assert abs(surface.volatility(100, 1.5) - 0.3) < 1e-12

    state = MarketState()
    await seed_market_state(state)
    engine = PricingEngine(state, workers=1)
    request = PriceRequest(symbol="CL", strike=80, maturity=0.5)
    first = await engine.price(request)
    second = await engine.price(request)
    assert not first.cached and second.cached
    await state.update(MarketTick(symbol="CL", futures_price=81, volatility=0.32))
    third = await engine.price(request)
    assert not third.cached and third.market_version == first.market_version + 1
    report = engine.latencies.report()
    assert report["black76_fast_path"].count == 2
    assert report["cache_hit"].count == 1
    engine.close()
    print("all smoke assertions passed")


if __name__ == "__main__":
    asyncio.run(main())
