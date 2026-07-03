"""Profiler unit tests on real DataFrames."""
import pandas as pd

from analysis.profiler import profile_dataframe


def _df():
    return pd.DataFrame(
        {
            "region": ["West", "East", "West", "East"],
            "revenue": [100, 200, 150, 50],
            "note": ["a", None, None, "d"],
        }
    )


def test_profile_shape_and_counts():
    p = profile_dataframe(_df())
    assert p["row_count"] == 4
    assert p["column_count"] == 3
    cols = {c["name"]: c for c in p["columns"]}
    assert cols["revenue"]["dtype"] == "integer"
    assert cols["region"]["dtype"] == "string"
    assert cols["region"]["distinct"] == 2
    assert cols["revenue"]["min"] == 50
    assert cols["revenue"]["max"] == 200


def test_profile_flags_duplicates():
    df = pd.DataFrame({"a": [1, 1, 2], "b": ["x", "x", "y"]})
    p = profile_dataframe(df)
    assert p["duplicate_rows"] == 1
    assert any("duplicate" in f for f in p["flags"])


def test_profile_empty_dataframe():
    df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    p = profile_dataframe(df)
    assert p["row_count"] == 0
    assert p["column_count"] == 1
    assert p["columns"][0]["null_pct"] == 0.0


def test_profile_high_null_flag():
    df = pd.DataFrame({"a": [1, None, None, None, None]})
    p = profile_dataframe(df)
    assert any("null" in f for f in p["flags"])
