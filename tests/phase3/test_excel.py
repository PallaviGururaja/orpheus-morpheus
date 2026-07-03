"""Phase 3 — Excel (.xlsx) ingestion.

Runs against the REAL production PostgreSQL driver (from .env) and the real
in-process pandas/openpyxl stack. Excel workbooks must load — first sheet by
default, or a chosen sheet — flow through the identical profiler + persistence
path as CSV, and behave identically downstream (a deterministic aggregate).
"""
import io
import shutil
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import pytest

from analysis.engine import load_dataframe, source_type_for


def _sales_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["West", "East", "West", "North"],
            "revenue": [100, 200, 150, 300],
            "units": [4, 7, 5, 9],
        }
    )


def _write_workbook(path: Path, *, extra_sheet: bool = False) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _sales_frame().to_excel(writer, sheet_name="Sales", index=False)
        if extra_sheet:
            pd.DataFrame({"country": ["IN", "US"], "count": [11, 22]}).to_excel(
                writer, sheet_name="Regions", index=False
            )


def _xlsx_bytes(*, extra_sheet: bool = False) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        _sales_frame().to_excel(writer, sheet_name="Sales", index=False)
        if extra_sheet:
            pd.DataFrame({"country": ["IN", "US"], "count": [11, 22]}).to_excel(
                writer, sheet_name="Regions", index=False
            )
    return buf.getvalue()


# --------------------------------------------------------------------------
# Loader-level tests (the shared ingest function)
# --------------------------------------------------------------------------


def test_load_dataframe_reads_first_excel_sheet(tmp_path):
    """Happy path: .xlsx loads with correct columns, dtypes and row count."""
    wb = tmp_path / "sales.xlsx"
    _write_workbook(wb, extra_sheet=True)

    df = load_dataframe(str(wb))

    assert list(df.columns) == ["region", "revenue", "units"]
    assert len(df) == 4
    assert pd.api.types.is_integer_dtype(df["revenue"])
    assert df["region"].tolist() == ["West", "East", "West", "North"]
    assert source_type_for(str(wb)) == "excel"


def test_load_dataframe_selects_named_and_indexed_sheet(tmp_path):
    """A chosen non-default sheet (by name and by index) loads the right data."""
    wb = tmp_path / "multi.xlsx"
    _write_workbook(wb, extra_sheet=True)

    by_name = load_dataframe(str(wb), sheet="Regions")
    assert list(by_name.columns) == ["country", "count"]
    assert by_name["country"].tolist() == ["IN", "US"]

    by_index = load_dataframe(str(wb), sheet="1")
    assert list(by_index.columns) == ["country", "count"]


def test_load_dataframe_unknown_sheet_raises(tmp_path):
    """Edge/error: an unknown sheet raises ValueError (mapped to 400 at the API)."""
    wb = tmp_path / "sales.xlsx"
    _write_workbook(wb)
    with pytest.raises(ValueError):
        load_dataframe(str(wb), sheet="DoesNotExist")


# --------------------------------------------------------------------------
# API: POST /datasets (multipart) with .xlsx
# --------------------------------------------------------------------------


def test_upload_excel_via_datasets_and_aggregate(api_client):
    """Happy path end-to-end: upload .xlsx, profile is correct, and a
    deterministic aggregate over the persisted dataset works identically."""
    content = _xlsx_bytes(extra_sheet=True)
    resp = api_client.post(
        "/datasets",
        files={
            "file": (
                "sales.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["row_count"] == 4
    assert data["column_count"] == 3
    names = [c["name"] for c in data["profile"]["columns"]]
    assert names == ["region", "revenue", "units"]
    rev = next(c for c in data["profile"]["columns"] if c["name"] == "revenue")
    assert rev["dtype"] == "integer"

    dataset_id = data["dataset_id"]

    # Downstream: a deterministic aggregate must work over the Excel dataset,
    # proving it behaves identically to a CSV once persisted.
    agg = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": dataset_id,
            "dimensions": ["region"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "bar",
        },
    )
    assert agg.status_code == 200, agg.text
    rows = agg.json()["data"]["rows"]
    west = next(r for r in rows if r["region"] == "West")
    assert west["revenue"] == 250  # 100 + 150


def test_upload_excel_selects_named_sheet(api_client):
    """A chosen non-default `sheet` form field loads the right sheet."""
    content = _xlsx_bytes(extra_sheet=True)
    resp = api_client.post(
        "/datasets",
        data={"sheet": "Regions"},
        files={
            "file": (
                "multi.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    names = [c["name"] for c in resp.json()["data"]["profile"]["columns"]]
    assert names == ["country", "count"]


def test_upload_unknown_sheet_is_400(api_client):
    """Error path: an unknown sheet is rejected with 400, not a 500."""
    content = _xlsx_bytes()
    resp = api_client.post(
        "/datasets",
        data={"sheet": "Nope"},
        files={
            "file": (
                "sales.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 400, resp.text


def test_reject_unsupported_extension(api_client):
    """Error path: a non-CSV / non-Excel file is still rejected with 400."""
    resp = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400, resp.text


# --------------------------------------------------------------------------
# API: GET /local/browse lists .xlsx + POST /datasets/local loads it
# --------------------------------------------------------------------------


@pytest.fixture
def home_workbook():
    """Write an .xlsx under a temp folder inside the home dir (home-confined)."""
    home = Path.home()
    d = Path(tempfile.mkdtemp(prefix="xlsx_test_", dir=str(home)))
    wb = d / "local_sales.xlsx"
    _write_workbook(wb)
    try:
        yield wb
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_local_browse_lists_and_loads_xlsx(api_client, home_workbook):
    """GET /local/browse lists the .xlsx; POST /datasets/local loads it by path."""
    folder = str(home_workbook.parent)
    browse = api_client.get("/local/browse", params={"path": folder})
    assert browse.status_code == 200, browse.text
    listed = [f["name"] for f in browse.json()["data"]["files"]]
    assert "local_sales.xlsx" in listed

    load = api_client.post(
        "/datasets/local", json={"path": str(home_workbook), "session_id": None}
    )
    assert load.status_code == 200, load.text
    data = load.json()["data"]
    assert data["row_count"] == 4
    assert [c["name"] for c in data["profile"]["columns"]] == [
        "region",
        "revenue",
        "units",
    ]


def test_local_load_rejects_unsupported_extension(api_client):
    """POST /datasets/local still rejects a non-CSV/non-Excel path with 400."""
    home = Path.home()
    d = Path(tempfile.mkdtemp(prefix="txt_test_", dir=str(home)))
    junk = d / f"{uuid.uuid4().hex}.txt"
    junk.write_text("not a dataset")
    try:
        resp = api_client.post(
            "/datasets/local", json={"path": str(junk), "session_id": None}
        )
        assert resp.status_code == 400, resp.text
    finally:
        shutil.rmtree(d, ignore_errors=True)
