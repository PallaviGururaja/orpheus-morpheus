"""Phase 3 dashboard-backend slice — deterministic aggregation + CRUD.

Runs against the REAL production PostgreSQL driver (from .env). NO LLM is
involved in any endpoint under test — aggregation is pure pandas over the
on-disk dataset file, so these tests need no Ollama/Gemini fixture.

The `_clean_db` autouse fixture (tests/conftest.py) truncates
`queries, datasets, sessions CASCADE`; the `dashboards` FK → sessions
(ondelete CASCADE) means dashboard rows are cleared with their session.
"""
import pandas as pd
import pytest

# A fixture with SEVERAL dimension groups so a wrong grouping is observable.
#   region×category sums of revenue:
#     West/A: 100 + 50  = 150
#     West/B: 200       = 200
#     East/A: 300       = 300
#     East/B: 400 + 10  = 410
#   region sums:  West=350, East=710
#   count by region: West=3, East=3
SALES_CSV = (
    "region,category,revenue,units\n"
    "West,A,100,4\n"
    "West,B,200,7\n"
    "East,A,300,9\n"
    "East,B,400,2\n"
    "West,A,50,1\n"
    "East,B,10,3\n"
).encode("utf-8")


@pytest.fixture
def upload(api_client):
    def _upload(csv_bytes: bytes = SALES_CSV, name: str = "sales.csv") -> dict:
        r = api_client.post(
            "/datasets", files={"file": (name, csv_bytes, "text/csv")}
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]

    return _upload


# --------------------------------------------------------------------------- #
# 1) Happy path — sum(revenue) by region×category matches hand-computed pandas.
# --------------------------------------------------------------------------- #
def test_aggregate_sum_by_dimensions_matches_hand_computed(api_client, upload):
    ds = upload()

    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region", "category"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "bar",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    # Hand-computed ground truth.
    df = pd.read_csv(pd.io.common.BytesIO(SALES_CSV))
    expected = (
        df.groupby(["region", "category"])["revenue"].sum().reset_index()
    )
    expected_map = {
        (row["region"], row["category"]): int(row["revenue"])
        for _, row in expected.iterrows()
    }

    got_map = {
        (row["region"], row["category"]): int(row["revenue"]) for row in data["rows"]
    }
    assert got_map == expected_map
    assert got_map[("West", "A")] == 150
    assert got_map[("East", "B")] == 410
    assert data["truncated"] is False
    assert data["agg"] == "sum"
    assert data["chart_type"] == "bar"
    assert data["row_count"] == len(expected)


def test_aggregate_single_dimension_sum(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "table",
        },
    )
    assert r.status_code == 200, r.text
    got = {row["region"]: int(row["revenue"]) for row in r.json()["data"]["rows"]}
    assert got == {"West": 350, "East": 710}


# --------------------------------------------------------------------------- #
# 2) Edge — count with measure=null groups per dimension correctly; and the
#    whole-dataset (no dimensions) aggregate returns one row.
# --------------------------------------------------------------------------- #
def test_aggregate_count_null_measure_groups_rows(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region"],
            "measure": None,
            "agg": "count",
            "chart_type": "pie",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    got = {row["region"]: int(row["count"]) for row in data["rows"]}
    assert got == {"West": 3, "East": 3}


def test_aggregate_no_dimensions_single_row(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": [],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "table",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["rows"]) == 1
    assert int(data["rows"][0]["revenue"]) == 1060  # total of all revenue


# --------------------------------------------------------------------------- #
# 3) Error paths — bad column, null measure with non-count agg, non-numeric
#    measure, unknown dataset, bad agg.
# --------------------------------------------------------------------------- #
def test_aggregate_unknown_column_400(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["does_not_exist"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "bar",
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "BAD_REQUEST"


def test_aggregate_null_measure_non_count_400(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region"],
            "measure": None,
            "agg": "sum",
            "chart_type": "bar",
        },
    )
    assert r.status_code == 400, r.text


def test_aggregate_non_numeric_measure_400(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region"],
            "measure": "category",  # a string column
            "agg": "sum",
            "chart_type": "bar",
        },
    )
    assert r.status_code == 400, r.text


def test_aggregate_unknown_dataset_404(api_client):
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": "no-such-dataset",
            "dimensions": ["region"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "bar",
        },
    )
    assert r.status_code == 404, r.text


def test_aggregate_bad_agg_400(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region"],
            "measure": "revenue",
            "agg": "median",
            "chart_type": "bar",
        },
    )
    assert r.status_code == 400, r.text


def test_aggregate_bad_chart_type_400(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboard/aggregate",
        json={
            "dataset_id": ds["dataset_id"],
            "dimensions": ["region"],
            "measure": "revenue",
            "agg": "sum",
            "chart_type": "heatmap",
        },
    )
    assert r.status_code == 400, r.text


# --------------------------------------------------------------------------- #
# 4) Dashboard CRUD round-trip — save → list → get → update → delete; widgets
#    JSONB persists byte-identically.
# --------------------------------------------------------------------------- #
WIDGETS = [
    {
        "id": "w1",
        "dimensions": ["region"],
        "measure": "revenue",
        "agg": "sum",
        "chart_type": "bar",
        "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
    },
    {
        "id": "w2",
        "dimensions": ["category"],
        "measure": None,
        "agg": "count",
        "chart_type": "pie",
        "layout": {"x": 6, "y": 0, "w": 6, "h": 4},
    },
]


def test_dashboard_crud_round_trip(api_client, upload):
    ds = upload()
    session_id = ds["session_id"]

    # Create.
    r = api_client.post(
        "/dashboards",
        json={"session_id": session_id, "name": "Sales overview", "widgets": WIDGETS},
    )
    assert r.status_code == 200, r.text
    created = r.json()["data"]
    dash_id = created["id"]
    assert created["name"] == "Sales overview"
    assert created["widgets"] == WIDGETS

    # List (filtered by session).
    r = api_client.get("/dashboards", params={"session_id": session_id})
    assert r.status_code == 200, r.text
    listed = r.json()["data"]["dashboards"]
    assert any(d["id"] == dash_id and d["name"] == "Sales overview" for d in listed)

    # Get — full widgets JSONB survives round-trip byte-identically.
    r = api_client.get(f"/dashboards/{dash_id}")
    assert r.status_code == 200, r.text
    got = r.json()["data"]
    assert got["widgets"] == WIDGETS
    assert got["session_id"] == session_id

    # Update name + widgets.
    new_widgets = WIDGETS[:1]
    r = api_client.put(
        f"/dashboards/{dash_id}",
        json={"name": "Renamed", "widgets": new_widgets},
    )
    assert r.status_code == 200, r.text
    updated = r.json()["data"]
    assert updated["name"] == "Renamed"
    assert updated["widgets"] == new_widgets

    # Confirm persistence of the update.
    r = api_client.get(f"/dashboards/{dash_id}")
    assert r.json()["data"]["widgets"] == new_widgets
    assert r.json()["data"]["name"] == "Renamed"

    # Delete.
    r = api_client.delete(f"/dashboards/{dash_id}")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["deleted"] is True

    # Gone.
    r = api_client.get(f"/dashboards/{dash_id}")
    assert r.status_code == 404, r.text


def test_dashboard_create_unknown_session_404(api_client):
    r = api_client.post(
        "/dashboards",
        json={"session_id": "no-such-session", "name": "X", "widgets": []},
    )
    assert r.status_code == 404, r.text


def test_dashboard_create_missing_name_400(api_client, upload):
    ds = upload()
    r = api_client.post(
        "/dashboards",
        json={"session_id": ds["session_id"], "name": "   ", "widgets": []},
    )
    assert r.status_code == 400, r.text


def test_dashboard_get_unknown_404(api_client):
    r = api_client.get("/dashboards/no-such-dashboard")
    assert r.status_code == 404, r.text
