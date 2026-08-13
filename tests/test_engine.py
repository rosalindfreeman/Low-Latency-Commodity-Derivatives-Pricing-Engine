import pytest

from commodity_engine.engine import PricingEngine
from commodity_engine.market import MarketState, seed_market_state
from commodity_engine.models import MarketTick, PriceRequest


@pytest.mark.asyncio
async def test_engine_caches_by_market_version() -> None:
    state = MarketState()
    await seed_market_state(state)
    engine = PricingEngine(state, workers=1)
    request = PriceRequest(symbol="CL", strike=80, maturity=0.5)
    first = await engine.price(request)
    second = await engine.price(request)
    assert not first.cached
    assert second.cached
    await state.update(MarketTick(symbol="CL", futures_price=81, volatility=0.32))
    third = await engine.price(request)
    assert not third.cached
    assert third.market_version == first.market_version + 1
    engine.close()


@pytest.mark.asyncio
async def test_unknown_symbol() -> None:
    state = MarketState()
    engine = PricingEngine(state, workers=1)
    with pytest.raises(KeyError):
        await engine.price(PriceRequest(symbol="NOPE", strike=1, maturity=1))
    engine.close()
