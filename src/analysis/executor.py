"""Restricted-namespace executor for agent-generated Python.

Runs generated code with the dataset pre-bound as a DataFrame ``df`` and a DuckDB
connection ``con``. Blocks filesystem / process / network access. This is a
pragmatic guardrail for a single-user local tool, not a hardened sandbox.
"""
import builtins
import io
import math
from contextlib import redirect_stdout
from typing import Any

import duckdb
import numpy as np
import pandas as pd

_BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "ctypes",
    "multiprocessing",
    "importlib",
    "pickle",
}

_ALLOWED_MODULES = {
    "pandas",
    "numpy",
    "duckdb",
    "math",
    "statistics",
    "datetime",
    "json",
    "re",
    "collections",
    "itertools",
    "functools",
}


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if root in _BLOCKED_MODULES:
        raise ImportError(f"Import of '{name}' is blocked in the analysis sandbox")
    if root not in _ALLOWED_MODULES:
        raise ImportError(f"Import of '{name}' is not permitted in the analysis sandbox")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _blocked_open(*args, **kwargs):
    raise PermissionError("File access ('open') is blocked in the analysis sandbox")


def _safe_builtins() -> dict:
    allowed_names = [
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter",
        "float", "format", "frozenset", "int", "isinstance", "issubclass", "len",
        "list", "map", "max", "min", "next", "print", "range", "reversed", "round",
        "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip", "repr",
        "True", "False", "None", "Exception", "ValueError", "TypeError", "KeyError",
        "IndexError", "ZeroDivisionError",
    ]
    safe = {n: getattr(builtins, n) for n in allowed_names if hasattr(builtins, n)}
    safe["__import__"] = _guarded_import
    safe["open"] = _blocked_open
    return safe


def _to_result_table(result: Any) -> list[dict]:
    """Coerce a result into JSON-serialisable summary-table rows (bounded)."""
    if result is None:
        return []
    if isinstance(result, pd.DataFrame):
        df = result.head(200)
    elif isinstance(result, pd.Series):
        df = result.head(200).reset_index()
        if df.shape[1] == 2:
            df.columns = [str(c) for c in df.columns]
    elif isinstance(result, dict):
        try:
            df = pd.DataFrame([{"key": k, "value": v} for k, v in result.items()]).head(200)
        except Exception:
            return [{"value": str(result)}]
    elif isinstance(result, (list, tuple)):
        try:
            df = pd.DataFrame(list(result)).head(200)
        except Exception:
            return [{"value": str(result)}]
    else:
        # scalar
        val = result
        if isinstance(val, (np.integer,)):
            val = int(val)
        elif isinstance(val, (np.floating,)):
            val = float(val)
        if isinstance(val, float) and not math.isfinite(val):
            val = None
        return [{"value": val}]

    df = df.where(pd.notna(df), None)
    rows = df.to_dict(orient="records")
    # normalise numpy scalars
    out: list[dict] = []
    for row in rows:
        clean: dict = {}
        for k, v in row.items():
            if isinstance(v, (np.integer,)):
                v = int(v)
            elif isinstance(v, (np.floating,)):
                v = float(v)
            elif isinstance(v, (np.bool_,)):
                v = bool(v)
            elif hasattr(v, "item"):
                try:
                    v = v.item()
                except Exception:
                    v = str(v)
            # JSON/JSONB cannot represent NaN or Inf. This catches both numpy
            # floats (coerced above) and native Python floats that to_dict emits
            # for null-containing columns — otherwise Postgres rejects the row.
            if isinstance(v, float) and not math.isfinite(v):
                v = None
            clean[str(k)] = v
        out.append(clean)
    return out


def execute_python(
    code: str,
    df: pd.DataFrame | None = None,
    tables: dict[str, pd.DataFrame] | None = None,
) -> dict:
    """Execute generated code; never raises. Returns captured result + error.

    Two forms are supported:

    * **Single-dataset (Phase 1):** pass ``df`` — the namespace exposes ``df``
      (a copy) and a DuckDB table ``df``.
    * **Multi-dataset (Phase 2):** pass ``tables`` — a ``{name: DataFrame}`` map.
      Each frame is registered as a DuckDB table ``name`` and exposed as a
      same-named namespace variable so generated code can JOIN/COMPARE/UNION
      across them. For back-compat, ``df`` is also bound to the FIRST table.

    In both cases ``pd``, ``np`` and a DuckDB connection ``con`` are available.
    The code is expected to assign to ``result``.
    """
    # Normalise both forms into an ordered {name: DataFrame} map.
    if tables is None:
        tables = {}
    else:
        tables = dict(tables)  # preserve caller order, own copy
    if df is not None and "df" not in tables:
        # Single-dataset form (or explicit df override): make it the first table.
        tables = {"df": df, **tables}
    if not tables:
        raise ValueError("execute_python requires a `df` or a non-empty `tables` map.")

    con = duckdb.connect(database=":memory:")
    namespace: dict = {
        "__builtins__": _safe_builtins(),
        "pd": pd,
        "np": np,
        "con": con,
        "duckdb": duckdb,
    }
    for name, frame in tables.items():
        try:
            con.register(name, frame)
        except Exception:
            pass
        namespace[name] = frame.copy()
    # Back-compat: expose the first table as `df` if not already named so.
    if "df" not in namespace:
        first_frame = next(iter(tables.values()))
        namespace["df"] = first_frame.copy()
        try:
            con.register("df", first_frame)
        except Exception:
            pass

    stdout_buf = io.StringIO()
    result_error: str | None = None
    try:
        with redirect_stdout(stdout_buf):
            exec(code, namespace)  # noqa: S102 — restricted namespace, local single-user tool
    except Exception as exc:  # capture, never raise to the graph
        result_error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            con.close()
        except Exception:
            pass

    result = namespace.get("result")
    if result_error is None and "result" not in namespace:
        result_error = "Code did not assign a `result` variable."

    result_table: list[dict] = []
    result_repr = ""
    if result_error is None:
        try:
            result_table = _to_result_table(result)
            result_repr = repr(result)[:2000]
        except Exception as exc:
            result_error = f"Result serialisation failed: {type(exc).__name__}: {exc}"

    return {
        "exec_stdout": stdout_buf.getvalue()[:5000],
        "exec_error": result_error,
        "result_repr": result_repr,
        "result_table": result_table,
    }
