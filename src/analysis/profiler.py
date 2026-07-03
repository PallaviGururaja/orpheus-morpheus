"""Dataset profiler: columns, dtypes, ranges, null/dup flags."""
from typing import Any

import pandas as pd


def _dtype_label(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def _json_safe(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    # numpy scalars expose .item() -> native Python scalar
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Compute a JSON-serialisable profile of a DataFrame."""
    row_count = int(len(df))
    columns: list[dict] = []

    for name in df.columns:
        series = df[name]
        null_count = int(series.isna().sum())
        null_pct = round(null_count / row_count, 4) if row_count else 0.0
        dtype = _dtype_label(series)

        col: dict[str, Any] = {
            "name": str(name),
            "dtype": dtype,
            "null_pct": null_pct,
            "null_count": null_count,
            "distinct": int(series.nunique(dropna=True)),
        }

        if dtype in ("integer", "float") and series.notna().any():
            col["min"] = _json_safe(series.min())
            col["max"] = _json_safe(series.max())

        columns.append(col)

    duplicate_rows = int(df.duplicated().sum())

    flags: list[str] = []
    if duplicate_rows:
        flags.append(f"{duplicate_rows} duplicate rows")
    high_null = [c["name"] for c in columns if c["null_pct"] >= 0.2]
    for name in high_null:
        flags.append(f"column '{name}' has high null rate")

    return {
        "columns": columns,
        "row_count": row_count,
        "column_count": int(df.shape[1]),
        "duplicate_rows": duplicate_rows,
        "flags": flags,
    }
