"""Deterministic dashboard aggregation — pandas group-by over a loaded dataset.

NO LLM. This is the Phase-3 dashboard headline compute path: it loads a dataset
from disk (the same on-disk store the ask/execute path uses) and computes a
single group-by aggregate for one dashboard widget. Kept separate from
``executor.py`` (which runs *agent-generated* code) — this module never execs
arbitrary code; it only calls pandas aggregation primitives.
"""
import math
from typing import Any

import numpy as np
import pandas as pd

from analysis.engine import load_csv

VALID_AGGS = {"sum", "avg", "count", "min", "max"}
VALID_CHART_TYPES = {"bar", "line", "scatter", "pie", "table"}

# Output-row cap; overflow sets ``truncated=True``.
ROW_CAP = 1000

# pandas aggregation function names keyed by our ``agg`` verbs.
_AGG_FUNCS = {"sum": "sum", "avg": "mean", "count": "count", "min": "min", "max": "max"}


class AggregationError(ValueError):
    """Raised for a caller/validation error (maps to HTTP 400)."""


def _json_safe_scalar(v: Any) -> Any:
    """Coerce a single value to a JSON/JSONB-safe Python scalar (NaN/Inf → None)."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        v = int(v)
    elif isinstance(v, (np.floating,)):
        v = float(v)
    elif isinstance(v, (np.bool_,)):
        return bool(v)
    elif hasattr(v, "item") and not isinstance(v, (str, bytes)):
        try:
            v = v.item()
        except Exception:
            return str(v)
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def _profile_columns(profile: dict) -> dict[str, str]:
    """Return ``{column_name: dtype}`` from a stored dataset profile."""
    cols: dict[str, str] = {}
    for c in (profile or {}).get("columns", []) or []:
        name = c.get("name")
        if name is not None:
            cols[str(name)] = str(c.get("dtype", ""))
    return cols


def aggregate(
    df: pd.DataFrame,
    profile: dict,
    dimensions: list[str],
    measure: str | None,
    agg: str,
) -> dict:
    """Compute one deterministic group-by aggregate over ``df``.

    Validates against the stored ``profile`` (every named column must exist,
    ``measure`` numeric unless ``agg='count'``). Returns ``{columns, rows,
    row_count, truncated}``. Raises :class:`AggregationError` (→ 400) on any
    validation failure.
    """
    dimensions = list(dimensions or [])

    if agg not in VALID_AGGS:
        raise AggregationError(
            f"Unknown agg '{agg}'. Must be one of {sorted(VALID_AGGS)}."
        )

    prof_cols = _profile_columns(profile)

    # Every named column must exist in the dataset profile.
    for col in dimensions:
        if col not in prof_cols:
            raise AggregationError(f"Column '{col}' is not in the dataset profile.")
    if measure is not None and measure not in prof_cols:
        raise AggregationError(f"Column '{measure}' is not in the dataset profile.")

    # measure / agg consistency.
    if agg == "count":
        # count works with or without a measure; a null measure counts rows.
        pass
    else:
        if measure is None:
            raise AggregationError(
                f"agg '{agg}' requires a measure column (measure was null)."
            )
        if prof_cols.get(measure) not in ("integer", "float"):
            raise AggregationError(
                f"Measure '{measure}' is not numeric (agg '{agg}' needs a numeric column)."
            )

    # Guard against columns present in the profile but missing from the frame.
    for col in dimensions:
        if col not in df.columns:
            raise AggregationError(f"Column '{col}' is not in the dataset.")
    if measure is not None and measure not in df.columns:
        raise AggregationError(f"Column '{measure}' is not in the dataset.")

    func = _AGG_FUNCS[agg]

    # Output column name for the aggregated value.
    if agg == "count":
        value_col = "count" if (measure is None or measure in dimensions) else measure
    else:
        value_col = measure  # type: ignore[assignment]

    if dimensions:
        grouped = df.groupby(dimensions, dropna=False)
        if agg == "count":
            series = grouped.size() if measure is None else grouped[measure].count()
        else:
            series = grouped[measure].agg(func)
        result = series.reset_index(name=value_col)
    else:
        # Whole-dataset single-row aggregate.
        if agg == "count":
            value = int(len(df)) if measure is None else int(df[measure].count())
        else:
            value = getattr(df[measure], func)()
        result = pd.DataFrame([{value_col: value}])

    total_rows = int(len(result))
    truncated = total_rows > ROW_CAP
    if truncated:
        result = result.head(ROW_CAP)

    columns = [str(c) for c in result.columns]
    rows: list[dict] = []
    for rec in result.to_dict(orient="records"):
        rows.append({str(k): _json_safe_scalar(v) for k, v in rec.items()})

    return {
        "columns": columns,
        "rows": rows,
        "row_count": total_rows if not truncated else ROW_CAP,
        "truncated": truncated,
    }


def load_dataset_dataframe(storage_path: str) -> pd.DataFrame:
    """Load a dataset's on-disk file into a DataFrame (same store as the ask path)."""
    return load_csv(storage_path)
