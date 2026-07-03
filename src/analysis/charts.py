"""Auto chart-type picker producing a neutral chart spec.

Returns {"type": "bar"|"line"|"scatter", "x": col, "y": col} or None.
The frontend renders this with recharts; the spec is renderer-neutral.
"""
from typing import Any

_NUMERIC = (int, float)


def _is_numeric_col(rows: list[dict], col: str) -> bool:
    seen = False
    for r in rows:
        v = r.get(col)
        if v is None:
            continue
        seen = True
        if isinstance(v, bool) or not isinstance(v, _NUMERIC):
            return False
    return seen


def _looks_temporal(name: str) -> bool:
    lname = name.lower()
    return any(k in lname for k in ("date", "time", "year", "month", "day", "week", "quarter"))


def select_chart(result_table: list[dict]) -> dict[str, Any] | None:
    """Pick a chart from result shape, or None when a chart is not sensible."""
    if not result_table or len(result_table) < 2:
        return None

    columns = list(result_table[0].keys())
    if len(columns) < 2:
        return None

    numeric_cols = [c for c in columns if _is_numeric_col(result_table, c)]
    category_cols = [c for c in columns if c not in numeric_cols]

    if not numeric_cols:
        return None

    y = numeric_cols[0]

    # scatter: two numeric axes
    if len(numeric_cols) >= 2 and not category_cols:
        return {"type": "scatter", "x": numeric_cols[0], "y": numeric_cols[1]}

    # pick an x axis: prefer a categorical / temporal column
    x = category_cols[0] if category_cols else columns[0]
    if x == y and len(numeric_cols) >= 2:
        y = numeric_cols[1]

    chart_type = "line" if _looks_temporal(x) else "bar"
    return {"type": chart_type, "x": x, "y": y}
