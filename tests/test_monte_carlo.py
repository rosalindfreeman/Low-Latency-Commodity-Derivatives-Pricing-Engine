import pytest

from commodity_engine.black76 import price
from commodity_engine.monte_carlo import asian_gbm, asian_ou


def test_asian_is_reproducible_across_chunks() -> None:
    kwargs = {
        "futures": 100,
        "strike": 100,
        "maturity": 1,
        "rate": 0.03,
        "volatility": 0.2,
        "paths": 10_000,
        "steps": 24,
        "seed": 12,
    }
    a = asian_gbm(**kwargs, chunk_size=10_000)
    b = asian_gbm(**kwargs, chunk_size=1_000)
    assert a.price == pytest.approx(b.price, abs=1e-12)
    assert a.standard_error == pytest.approx(b.standard_error, abs=1e-12)


def test_asian_call_is_below_corresponding_european_in_example() -> None:
    result = asian_gbm(100, 100, 1, 0.03, 0.2, paths=40_000, steps=48, seed=3)
    assert 0 < result.price < price(100, 100, 1, 0.03, 0.2)


def test_mean_reversion_pulls_average_toward_theta() -> None:
    result = asian_ou(100, 95, 1, 0, 3, kappa=8, theta=90, paths=20_000, steps=48, seed=5)
    assert result.price < 1.0
