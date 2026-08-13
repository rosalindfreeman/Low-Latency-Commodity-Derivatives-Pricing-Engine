from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class ModelType(StrEnum):
    BLACK76 = "black76"
    ASIAN_GBM = "asian_gbm"
    ASIAN_OU = "asian_ou"


class MarketTick(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    futures_price: float = Field(gt=0)
    rate: float = Field(default=0.04, ge=-0.1, le=1.0)
    volatility: float = Field(default=0.25, gt=0, le=5.0)
    timestamp_ns: int | None = None


class PriceRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    strike: float = Field(gt=0)
    maturity: float = Field(gt=0, le=30)
    option_type: OptionType = OptionType.CALL
    model: ModelType = ModelType.BLACK76
    paths: int = Field(default=100_000, ge=1_000, le=20_000_000)
    steps: int = Field(default=64, ge=2, le=2_000)
    chunk_size: int = Field(default=50_000, ge=100, le=2_000_000)
    seed: int = Field(default=42, ge=0)
    use_surface: bool = True
    run_in_process: bool = True
    kappa: float = Field(default=1.5, gt=0, le=50)
    theta: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_model(self) -> PriceRequest:
        if self.model == ModelType.BLACK76:
            self.run_in_process = False
        return self


class Greeks(BaseModel):
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


class PriceResponse(BaseModel):
    symbol: str
    model: ModelType
    price: float
    standard_error: float | None = None
    volatility: float
    market_version: int
    cached: bool
    latency_ms: float
    greeks: Greeks | None = None


class ScenarioRequest(BaseModel):
    base: PriceRequest
    spot_shocks: list[float] = Field(default=[-0.1, -0.05, 0.0, 0.05, 0.1], max_length=100)
    volatility_shocks: list[float] = Field(default=[-0.05, 0.0, 0.05], max_length=100)
    parallel: bool = True


class ScenarioResult(BaseModel):
    spot_shock: float
    volatility_shock: float
    price: float


class Subscription(BaseModel):
    symbol: str
    strike: float = Field(gt=0)
    maturity: float = Field(gt=0)
    option_type: OptionType = OptionType.CALL
    use_surface: bool = True
    interval_ms: int = Field(default=250, ge=25, le=60_000)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    instruments: int
    cache_entries: int

