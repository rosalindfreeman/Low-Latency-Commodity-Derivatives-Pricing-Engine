from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

import numpy as np

from commodity_engine.models import MarketTick
from commodity_engine.vol_surface import VolatilitySurface, default_surface


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    symbol: str
    futures_price: float
    rate: float
    volatility: float
    timestamp_ns: int
    version: int
    surface: VolatilitySurface | None = None


class MarketState:
    """Copy-on-write market state: readers never wait on a database or network."""

    def __init__(self) -> None:
        self._snapshots: dict[str, MarketSnapshot] = {}
        self._lock = asyncio.Lock()
        self._changed = asyncio.Condition()

    async def update(self, tick: MarketTick, surface: VolatilitySurface | None = None) -> MarketSnapshot:
        symbol = tick.symbol.upper()
        async with self._lock:
            previous = self._snapshots.get(symbol)
            snapshot = MarketSnapshot(
                symbol=symbol,
                futures_price=tick.futures_price,
                rate=tick.rate,
                volatility=tick.volatility,
                timestamp_ns=tick.timestamp_ns or time.time_ns(),
                version=1 if previous is None else previous.version + 1,
                surface=surface if surface is not None else (previous.surface if previous else None),
            )
            self._snapshots = {**self._snapshots, symbol: snapshot}
        async with self._changed:
            self._changed.notify_all()
        return snapshot

    def get(self, symbol: str) -> MarketSnapshot:
        try:
            return self._snapshots[symbol.upper()]
        except KeyError as exc:
            raise KeyError(f"unknown symbol: {symbol}") from exc

    def all(self) -> dict[str, MarketSnapshot]:
        return self._snapshots.copy()

    async def wait_for_change(self, symbol: str, after_version: int, timeout: float) -> MarketSnapshot:
        try:
            async with self._changed:
                await asyncio.wait_for(
                    self._changed.wait_for(lambda: self.get(symbol).version > after_version), timeout
                )
        except TimeoutError:
            pass
        return self.get(symbol)


DEFAULT_MARKETS = {
    "GC": (2400.0, 0.17),
    "SI": (29.0, 0.28),
    "CL": (78.0, 0.32),
    "NG": (3.1, 0.52),
}


async def seed_market_state(state: MarketState) -> None:
    for symbol, (price, vol) in DEFAULT_MARKETS.items():
        await state.update(
            MarketTick(symbol=symbol, futures_price=price, volatility=vol),
            default_surface(price, vol),
        )


async def simulated_feed(interval: float = 0.25, seed: int = 7) -> AsyncIterator[MarketTick]:
    """Async simulated feed; replace this adapter with an exchange/vendor client."""
    rng = np.random.default_rng(seed)
    prices = {symbol: price for symbol, (price, _) in DEFAULT_MARKETS.items()}
    while True:
        await asyncio.sleep(interval)
        ticks = []
        for symbol, price in prices.items():
            vol = DEFAULT_MARKETS[symbol][1]
            price *= math.exp(-0.5 * vol**2 / 252 + vol / math.sqrt(252) * rng.normal() * 0.05)
            prices[symbol] = price
            ticks.append(MarketTick(symbol=symbol, futures_price=price, volatility=vol))
        for tick in ticks:
            yield tick


async def consume_feed(state: MarketState, feed: AsyncIterator[MarketTick]) -> None:
    async for tick in feed:
        await state.update(tick)

