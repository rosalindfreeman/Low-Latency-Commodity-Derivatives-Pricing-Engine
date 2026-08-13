from commodity_engine.report_view import comparison_report_html


def test_comparison_report_renders_measured_results() -> None:
    report = comparison_report_html()
    assert "Time Consumption and Accuracy Comparison" in report
    assert "Asian GBM" in report
    assert "Time vs Black-76" in report
