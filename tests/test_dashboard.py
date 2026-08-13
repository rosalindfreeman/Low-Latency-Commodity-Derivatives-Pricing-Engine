from commodity_engine.dashboard import DASHBOARD_HTML


def test_dashboard_contains_pricing_controls() -> None:
    assert "RUN PRICING SIMULATION" in DASHBOARD_HTML
    assert 'id="model"' in DASHBOARD_HTML
    assert "asian_ou" in DASHBOARD_HTML
    assert "latency_ms" in DASHBOARD_HTML


def test_dashboard_chart_draws_single_observation_and_resizes() -> None:
    assert "points.length>1" in DASHBOARD_HTML
    assert "x.arc(p.x,p.y,4" in DASHBOARD_HTML
    assert "window.addEventListener('resize',draw)" in DASHBOARD_HTML
