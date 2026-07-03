"""Chart auto-picker tests."""
from analysis.charts import select_chart


def test_bar_for_category_numeric():
    rows = [{"region": "West", "revenue": 250}, {"region": "East", "revenue": 200}]
    spec = select_chart(rows)
    assert spec == {"type": "bar", "x": "region", "y": "revenue"}


def test_line_for_temporal():
    rows = [{"month": "2024-01", "revenue": 10}, {"month": "2024-02", "revenue": 20}]
    spec = select_chart(rows)
    assert spec["type"] == "line"
    assert spec["x"] == "month"


def test_scatter_for_two_numeric():
    rows = [{"x": 1.0, "y": 2.0}, {"x": 3.0, "y": 4.0}]
    spec = select_chart(rows)
    assert spec["type"] == "scatter"


def test_none_for_single_row():
    assert select_chart([{"region": "West", "revenue": 250}]) is None


def test_none_for_empty():
    assert select_chart([]) is None
