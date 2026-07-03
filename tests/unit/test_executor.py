"""Restricted-namespace executor tests — real pandas/duckdb, no LLM."""
import pandas as pd

from analysis.executor import execute_python


def _df():
    return pd.DataFrame(
        {"region": ["West", "East", "West"], "revenue": [100, 200, 150]}
    )


def test_happy_groupby():
    code = "result = df.groupby('region')['revenue'].sum().reset_index()"
    out = execute_python(code, _df())
    assert out["exec_error"] is None
    rows = {r["region"]: r["revenue"] for r in out["result_table"]}
    assert rows["West"] == 250
    assert rows["East"] == 200


def test_scalar_result():
    out = execute_python("result = int(df['revenue'].sum())", _df())
    assert out["exec_error"] is None
    assert out["result_table"] == [{"value": 450}]


def test_duckdb_available():
    code = "result = con.execute('SELECT sum(revenue) AS total FROM df').df()"
    out = execute_python(code, _df())
    assert out["exec_error"] is None
    assert out["result_table"][0]["total"] == 450


def test_missing_result_is_error():
    out = execute_python("x = 5", _df())
    assert out["exec_error"] is not None
    assert "result" in out["exec_error"]


def test_blocks_os_import():
    out = execute_python("import os\nresult = os.getcwd()", _df())
    assert out["exec_error"] is not None
    assert "blocked" in out["exec_error"].lower() or "not permitted" in out["exec_error"].lower()


def test_blocks_subprocess_import():
    out = execute_python("import subprocess\nresult = 1", _df())
    assert out["exec_error"] is not None


def test_blocks_open():
    out = execute_python("result = open('secret.txt')", _df())
    assert out["exec_error"] is not None
    assert "blocked" in out["exec_error"].lower()


def test_runtime_error_captured_not_raised():
    out = execute_python("result = df['missing_col'].sum()", _df())
    assert out["exec_error"] is not None  # captured, not raised
