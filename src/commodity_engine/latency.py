from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LatencySummary:
    count: int
    latest_ms: float
    minimum_ms: float
    average_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    maximum_ms: float


def _percentile(ordered: list[float], percentile: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


class LatencyTracker:
    """Bounded in-process latency recorder with a very small request-path cost."""

    def __init__(self, sample_size: int = 10_000) -> None:
        self._samples: dict[str, deque[float]] = {}
        self._totals: dict[str, int] = {}
        self._sample_size = sample_size
        self._lock = threading.Lock()

    def record(self, category: str, elapsed_ms: float) -> None:
        with self._lock:
            samples = self._samples.setdefault(category, deque(maxlen=self._sample_size))
            samples.append(elapsed_ms)
            self._totals[category] = self._totals.get(category, 0) + 1

    def report(self) -> dict[str, LatencySummary]:
        with self._lock:
            snapshot = {
                category: (list(samples), self._totals[category])
                for category, samples in self._samples.items()
            }
        report = {}
        for category, (samples, count) in snapshot.items():
            ordered = sorted(samples)
            report[category] = LatencySummary(
                count=count,
                latest_ms=samples[-1],
                minimum_ms=ordered[0],
                average_ms=sum(samples) / len(samples),
                p50_ms=_percentile(ordered, 0.50),
                p95_ms=_percentile(ordered, 0.95),
                p99_ms=_percentile(ordered, 0.99),
                maximum_ms=ordered[-1],
            )
        return report

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()
            self._totals.clear()

