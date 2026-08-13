import math

import pytest

from commodity_engine.black76 import greeks, price


def test_put_call_parity() -> None:
    futures, strike, maturity, rate, volatility = 100, 95, 0.75, 0.04, 0.3
    call = price(futures, strike, maturity, rate, volatility, "call")
    put = price(futures, strike, maturity, rate, volatility, "put")
    assert call - put == pytest.approx(math.exp(-rate * maturity) * (futures - strike))


def test_delta_matches_finite_difference() -> None:
    args = (100.0, 100.0, 1.0, 0.03, 0.2)
    analytical = greeks(*args, "call")
    h = 0.001
    finite_difference = (price(args[0] + h, *args[1:], "call") -
                         price(args[0] - h, *args[1:], "call")) / (2 * h)
    assert analytical.delta == pytest.approx(finite_difference, rel=1e-5)


def test_invalid_input() -> None:
    with pytest.raises(ValueError):
        price(100, 100, 0, 0.03, 0.2)

