from __future__ import annotations

import math

from commodity_engine.models import Greeks, OptionType

_SQRT_2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / _SQRT_2))


def _pdf(x: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * x * x)


def price(futures: float, strike: float, maturity: float, rate: float, volatility: float,
          option_type: OptionType | str = OptionType.CALL) -> float:
    """Black-76 price for a European option on a futures contract."""
    if min(futures, strike, maturity, volatility) <= 0:
        raise ValueError("futures, strike, maturity and volatility must be positive")
    sqrt_t = math.sqrt(maturity)
    d1 = (math.log(futures / strike) + 0.5 * volatility**2 * maturity) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    discount = math.exp(-rate * maturity)
    if OptionType(option_type) == OptionType.CALL:
        return discount * (futures * _cdf(d1) - strike * _cdf(d2))
    return discount * (strike * _cdf(-d2) - futures * _cdf(-d1))


def greeks(futures: float, strike: float, maturity: float, rate: float, volatility: float,
           option_type: OptionType | str = OptionType.CALL) -> Greeks:
    """Analytical Black-76 Greeks; theta is calendar-time decay, vega per vol point."""
    kind = OptionType(option_type)
    sqrt_t = math.sqrt(maturity)
    d1 = (math.log(futures / strike) + 0.5 * volatility**2 * maturity) / (volatility * sqrt_t)
    discount = math.exp(-rate * maturity)
    density = _pdf(d1)
    if kind == OptionType.CALL:
        delta = discount * _cdf(d1)
    else:
        delta = -discount * _cdf(-d1)
    gamma = discount * density / (futures * volatility * sqrt_t)
    vega = discount * futures * density * sqrt_t / 100.0
    option_price = price(futures, strike, maturity, rate, volatility, kind)
    theta = -(discount * futures * density * volatility / (2.0 * sqrt_t)) + rate * option_price
    rho = -maturity * option_price / 100.0
    return Greeks(delta=delta, gamma=gamma, vega=vega, theta=theta / 365.0, rho=rho)
