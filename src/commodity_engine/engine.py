from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

from commodity_engine import black76
from commodity_engine.cache import TTLCache
from commodity_engine.latency import LatencyTracker
from commodity_engine.market import MarketSnapshot, MarketState
from commodity_engine.models import (
    ModelType,
    PriceRequest,
    PriceResponse,
    ScenarioRequest,
    ScenarioResult,
)
from commodity_engine.monte_carlo import MonteCarloResult, asian_gbm, asian_ou


def _run_mc(request: PriceRequest, market: MarketSnapshot, volatility: float) -> MonteCarloResult:
    common = {
        "strike": request.strike,
        "maturity": request.maturity,
        "rate": market.rate,
        "volatility": volatility,
        "option_type": request.option_type,
        "paths": request.paths,
        "steps": request.steps,
        "chunk_size": request.chunk_size,
        "seed": request.seed,
    }
    if request.model == ModelType.ASIAN_GBM:
        return asian_gbm(futures=market.futures_price, **common)
    if request.model == ModelType.ASIAN_OU:
        # OU sigma has price units. A quoted relative vol is converted at the current level.
        return asian_ou(
            level=market.futures_price, kappa=request.kappa,
            theta=request.theta or market.futures_price,
            **{**common, "volatility": volatility * market.futures_price},
        )
    raise ValueError(f"unsupported Monte Carlo model: {request.model}")


def _scenario_worker(payload: tuple[PriceRequest, MarketSnapshot, float, float, float]) -> ScenarioResult:
    request, market, volatility, spot_shock, vol_shock = payload
    shocked = replace(market, futures_price=market.futures_price * (1.0 + spot_shock))
    shocked_vol = max(0.001, volatility + vol_shock)
    if request.model == ModelType.BLACK76:
        value = black76.price(shocked.futures_price, request.strike, request.maturity,
                              shocked.rate, shocked_vol, request.option_type)
    else:
        value = _run_mc(request, shocked, shocked_vol).price
    return ScenarioResult(spot_shock=spot_shock, volatility_shock=vol_shock, price=value)


class PricingEngine:
    def __init__(self, market_state: MarketState, workers: int | None = None) -> None:
        self.market_state = market_state
        self.cache: TTLCache[tuple[float, float | None]] = TTLCache(maxsize=20_000, ttl_seconds=30)
        self.latencies = LatencyTracker(sample_size=10_000)
        worker_count = workers if workers is not None else int(os.getenv("ENGINE_WORKERS", "2"))
        self.pool = ProcessPoolExecutor(max_workers=max(1, worker_count))

    @staticmethod
    def _volatility(request: PriceRequest, market: MarketSnapshot) -> float:
        if request.use_surface and market.surface is not None:
            return market.surface.volatility(request.strike, request.maturity)
        return market.volatility

    @staticmethod
    def _cache_key(request: PriceRequest, market: MarketSnapshot, volatility: float) -> tuple:
        return (market.symbol, market.version, round(volatility, 8), *request.model_dump().values())

    async def price(self, request: PriceRequest) -> PriceResponse:
        started = time.perf_counter_ns()
        market = self.market_state.get(request.symbol)
        volatility = self._volatility(request, market)
        key = self._cache_key(request, market, volatility)
        cached_value = self.cache.get(key)
        cached = cached_value is not None
        if cached_value is not None:
            value, standard_error = cached_value
        elif request.model == ModelType.BLACK76:
            value = black76.price(market.futures_price, request.strike, request.maturity,
                                  market.rate, volatility, request.option_type)
            standard_error = None
            self.cache.set(key, (value, standard_error))
        else:
            if request.run_in_process:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(self.pool, _run_mc, request, market, volatility)
            else:
                result = await asyncio.to_thread(_run_mc, request, market, volatility)
            value, standard_error = result.price, result.standard_error
            self.cache.set(key, (value, standard_error))
        analytical_greeks = None
        if request.model == ModelType.BLACK76:
            analytical_greeks = black76.greeks(
                market.futures_price, request.strike, request.maturity,
                market.rate, volatility, request.option_type,
            )
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        category = "cache_hit" if cached else (
            "black76_fast_path" if request.model == ModelType.BLACK76 else "monte_carlo_slow_path"
        )
        self.latencies.record(category, elapsed)
        return PriceResponse(
            symbol=market.symbol, model=request.model, price=value,
            standard_error=standard_error, volatility=volatility,
            market_version=market.version, cached=cached, latency_ms=elapsed,
            greeks=analytical_greeks,
        )

    async def scenarios(self, request: ScenarioRequest) -> list[ScenarioResult]:
        market = self.market_state.get(request.base.symbol)
        volatility = self._volatility(request.base, market)
        payloads = [
            (request.base, market, volatility, spot, vol)
            for spot in request.spot_shocks for vol in request.volatility_shocks
        ]
        if request.parallel and len(payloads) > 1:
            loop = asyncio.get_running_loop()
            futures = [loop.run_in_executor(self.pool, _scenario_worker, payload) for payload in payloads]
            return list(await asyncio.gather(*futures))
        return [_scenario_worker(payload) for payload in payloads]

    def close(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)
