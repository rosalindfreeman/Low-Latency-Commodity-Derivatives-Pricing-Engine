from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from commodity_engine.models import OptionType


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    price: float
    standard_error: float
    paths: int


def _finish(total: float, total_sq: float, paths: int, discount: float) -> MonteCarloResult:
    mean = total / paths
    variance = max(total_sq / paths - mean * mean, 0.0)
    return MonteCarloResult(discount * mean, discount * math.sqrt(variance / paths), paths)


def asian_gbm(futures: float, strike: float, maturity: float, rate: float, volatility: float,
              option_type: OptionType | str = OptionType.CALL, paths: int = 100_000,
              steps: int = 64, chunk_size: int = 50_000, seed: int = 42) -> MonteCarloResult:
    """Arithmetic-average Asian option using vectorised, chunked GBM simulation."""
    rng = np.random.default_rng(seed)
    dt = maturity / steps
    drift = -0.5 * volatility**2 * dt
    diffusion = volatility * math.sqrt(dt)
    sign = 1.0 if OptionType(option_type) == OptionType.CALL else -1.0
    total = total_sq = 0.0
    completed = 0
    while completed < paths:
        n = min(chunk_size, paths - completed)
        z = rng.standard_normal((n, steps))
        log_paths = np.cumsum(drift + diffusion * z, axis=1)
        average = (futures + np.exp(log_paths).sum(axis=1) * futures) / (steps + 1)
        payoff = np.maximum(sign * (average - strike), 0.0)
        total += float(payoff.sum())
        total_sq += float(np.dot(payoff, payoff))
        completed += n
    return _finish(total, total_sq, paths, math.exp(-rate * maturity))


def asian_ou(level: float, strike: float, maturity: float, rate: float, volatility: float,
             kappa: float, theta: float, option_type: OptionType | str = OptionType.CALL,
             paths: int = 100_000, steps: int = 64, chunk_size: int = 50_000,
             seed: int = 42) -> MonteCarloResult:
    """Asian option under exact-discretised Ornstein-Uhlenbeck level dynamics."""
    rng = np.random.default_rng(seed)
    dt = maturity / steps
    decay = math.exp(-kappa * dt)
    step_std = volatility * math.sqrt((1.0 - math.exp(-2.0 * kappa * dt)) / (2.0 * kappa))
    sign = 1.0 if OptionType(option_type) == OptionType.CALL else -1.0
    total = total_sq = 0.0
    completed = 0
    while completed < paths:
        n = min(chunk_size, paths - completed)
        values = np.full(n, level, dtype=float)
        running_sum = values.copy()
        for _ in range(steps):
            values = theta + (values - theta) * decay + step_std * rng.standard_normal(n)
            running_sum += values
        average = running_sum / (steps + 1)
        payoff = np.maximum(sign * (average - strike), 0.0)
        total += float(payoff.sum())
        total_sq += float(np.dot(payoff, payoff))
        completed += n
    return _finish(total, total_sq, paths, math.exp(-rate * maturity))
