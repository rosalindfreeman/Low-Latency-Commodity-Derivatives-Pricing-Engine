import pytest

from commodity_engine.latency import LatencyTracker


def test_latency_summary_and_request_count() -> None:
    tracker = LatencyTracker(sample_size=3)
    for value in [1.0, 2.0, 3.0, 4.0]:
        tracker.record("fast", value)
    result = tracker.report()["fast"]
    assert result.count == 4
    assert result.minimum_ms == 2.0
    assert result.maximum_ms == 4.0
    assert result.average_ms == pytest.approx(3.0)
    assert result.p50_ms == 3.0
