"""GET /queries/{id}/export — download a persisted query's result_table as CSV.

Runs against the real production PostgreSQL driver (from .env). Seeds a Query
row with a known result_table, exports it, and parses the CSV body back to
verify byte-level fidelity. No LLM involved (deterministic serialization).
"""
import csv
import io

from db.models import Query, Session as SessionRow
from db.session import create_db_session


def _seed_session() -> str:
    with create_db_session() as s:
        row = SessionRow(title="Export test")
        s.add(row)
        s.flush()
        return row.id


def _seed_query(result_table, question: str = "total revenue by region") -> str:
    """Insert a completed query with the given result_table; return its id."""
    session_id = _seed_session()
    with create_db_session() as s:
        row = Query(
            session_id=session_id,
            dataset_ids=["ds-1"],
            question=question,
            code="result = df.groupby('region')['revenue'].sum().reset_index()",
            result_table=result_table,
            answer_text="West leads.",
            status="completed",
            verified=True,
            steps_used=2,
        )
        s.add(row)
        s.flush()
        return row.id


def _parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_export_returns_csv_matching_result_table(api_client):
    """Happy path: CSV download with the right headers, content-type, and rows."""
    result = [
        {"region": "West", "revenue": 250},
        {"region": "East", "revenue": 250},
        {"region": "North", "revenue": 300},
    ]
    query_id = _seed_query(result)

    r = api_client.get(f"/queries/{query_id}/export")

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    disposition = r.headers["content-disposition"]
    assert "attachment" in disposition
    assert f"query-{query_id}.csv" in disposition

    parsed = _parse_csv(r.text)
    assert [row["region"] for row in parsed] == ["West", "East", "North"]
    assert [int(row["revenue"]) for row in parsed] == [250, 250, 300]
    # Header row is the table's keys.
    assert r.text.splitlines()[0] == "region,revenue"


def test_export_handles_null_and_mixed_cells(api_client):
    """Edge case: a None cell serializes to an empty field, ragged keys union."""
    result = [
        {"region": "West", "revenue": 100, "note": "top"},
        {"region": "East", "revenue": None},
    ]
    query_id = _seed_query(result)

    r = api_client.get(f"/queries/{query_id}/export")
    assert r.status_code == 200, r.text

    parsed = _parse_csv(r.text)
    # Union of keys across rows forms the header.
    assert set(parsed[0].keys()) == {"region", "revenue", "note"}
    assert parsed[0]["note"] == "top"
    # None revenue and missing note both render as empty strings.
    assert parsed[1]["revenue"] == ""
    assert parsed[1]["note"] == ""


def test_export_unknown_query_404(api_client):
    """Error path: unknown query id returns 404."""
    r = api_client.get("/queries/does-not-exist/export")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_export_no_result_table_400(api_client):
    """Error path: a query with no result table (failed run) returns 400."""
    query_id = _seed_query(None)
    r = api_client.get(f"/queries/{query_id}/export")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_REQUEST"


def test_export_empty_result_table_400(api_client):
    """Edge/error: an empty result table also has nothing to export (400)."""
    query_id = _seed_query([])
    r = api_client.get(f"/queries/{query_id}/export")
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Dashboard widget export — recompute the aggregate server-side, stream as CSV.
# --------------------------------------------------------------------------- #
_SAMPLE_CSV = (
    "region,revenue,units\n"
    "West,100,4\n"
    "East,200,7\n"
    "West,150,5\n"
    "East,50,2\n"
    "North,300,9\n"
).encode("utf-8")


def _upload_dataset(api_client) -> dict:
    r = api_client.post(
        "/datasets", files={"file": ("sales.csv", _SAMPLE_CSV, "text/csv")}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _create_dashboard(api_client, session_id: str, widgets: list) -> dict:
    r = api_client.post(
        "/dashboards",
        json={"session_id": session_id, "name": "Sales overview", "widgets": widgets},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_widget_export_matches_aggregate(api_client):
    """Happy path: widget CSV rows equal POST /dashboard/aggregate for the spec."""
    up = _upload_dataset(api_client)
    widget = {
        "id": "w1",
        "dataset_id": up["dataset_id"],
        "dimensions": ["region"],
        "measure": "revenue",
        "agg": "sum",
        "chart_type": "bar",
    }
    dash = _create_dashboard(api_client, up["session_id"], [widget])

    r = api_client.get(f"/dashboards/{dash['id']}/widgets/w1/export")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="widget-w1.csv"' in r.headers["content-disposition"]

    parsed = _parse_csv(r.text)
    by_region = {row["region"]: int(row["revenue"]) for row in parsed}
    assert by_region == {"West": 250, "East": 250, "North": 300}

    # Parity with the aggregate endpoint over the same spec.
    agg = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": up["dataset_id"],
            "dimensions": ["region"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "bar",
        },
    ).json()["data"]
    agg_by_region = {row["region"]: int(row["revenue"]) for row in agg["rows"]}
    assert agg_by_region == by_region


def test_widget_export_unknown_dashboard_404(api_client):
    """Error path: unknown dashboard id returns 404."""
    r = api_client.get("/dashboards/nope/widgets/w1/export")
    assert r.status_code == 404


def test_widget_export_unknown_widget_404(api_client):
    """Error path: unknown widget id within a real dashboard returns 404."""
    up = _upload_dataset(api_client)
    dash = _create_dashboard(
        api_client,
        up["session_id"],
        [{"id": "w1", "dataset_id": up["dataset_id"], "dimensions": [],
          "measure": "revenue", "agg": "sum", "chart_type": "bar"}],
    )
    r = api_client.get(f"/dashboards/{dash['id']}/widgets/ghost/export")
    assert r.status_code == 404
