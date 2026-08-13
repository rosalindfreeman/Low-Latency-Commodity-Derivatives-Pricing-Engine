from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class VolatilitySurface:
    """Dependency-light bilinear volatility surface with flat boundary extrapolation."""

    maturities: np.ndarray
    strikes: np.ndarray
    volatilities: np.ndarray

    def __post_init__(self) -> None:
        maturities = np.asarray(self.maturities, dtype=float)
        strikes = np.asarray(self.strikes, dtype=float)
        vols = np.asarray(self.volatilities, dtype=float)
        if vols.shape != (len(maturities), len(strikes)):
            raise ValueError("volatilities must have shape (maturities, strikes)")
        if np.any(np.diff(maturities) <= 0) or np.any(np.diff(strikes) <= 0):
            raise ValueError("maturities and strikes must be strictly increasing")
        if np.any(vols <= 0):
            raise ValueError("volatilities must be positive")
        object.__setattr__(self, "maturities", maturities)
        object.__setattr__(self, "strikes", strikes)
        object.__setattr__(self, "volatilities", vols)

    def volatility(self, strike: float, maturity: float) -> float:
        t = float(np.clip(maturity, self.maturities[0], self.maturities[-1]))
        k = float(np.clip(strike, self.strikes[0], self.strikes[-1]))
        strike_slice = np.array([
            np.interp(k, self.strikes, row) for row in self.volatilities
        ])
        return float(np.interp(t, self.maturities, strike_slice))


def default_surface(reference_price: float, base_volatility: float) -> VolatilitySurface:
    strikes = reference_price * np.array([0.7, 0.85, 1.0, 1.15, 1.3])
    maturities = np.array([1 / 12, 0.25, 0.5, 1.0, 2.0])
    smile = np.array([0.08, 0.025, 0.0, 0.015, 0.055])
    term = np.array([0.04, 0.025, 0.015, 0.0, -0.01])
    vols = np.maximum(0.01, base_volatility + term[:, None] + smile[None, :])
    return VolatilitySurface(maturities, strikes, vols)
