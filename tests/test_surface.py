import numpy as np
import pytest

from commodity_engine.vol_surface import VolatilitySurface


def test_bilinear_interpolation() -> None:
    surface = VolatilitySurface(
        np.array([1.0, 2.0]), np.array([90.0, 110.0]), np.array([[0.2, 0.3], [0.3, 0.4]])
    )
    assert surface.volatility(100, 1.5) == pytest.approx(0.3)


def test_flat_extrapolation() -> None:
    surface = VolatilitySurface(
        np.array([1.0, 2.0]), np.array([90.0, 110.0]), np.array([[0.2, 0.3], [0.3, 0.4]])
    )
    assert surface.volatility(1, 0.1) == pytest.approx(0.2)

