"""Multi-dataset (JOIN/UNION) analysis — REAL Ollama + REAL PostgreSQL.

The headline test uses two related CSVs (orders + customers) where the correct
answer REQUIRES the join: no single table alone can produce it, and a naive
single-table number is observably different from the joined answer.
"""
import pandas as pd
import pytest

from analysis.executor import execute_python
from db.models import Query
from db.session import create_db_session

# --------------------------------------------------------------------------- #
# Two related datasets. Premium customers are 1 and 3.
#   cust 1 orders: 100 + 50  = 150
#   cust 3 orders: 300 + 25  = 325
#   Premium total           = 475   <-- requires the JOIN
#   Standard total (2,4)    = 200 + 400 = 600
#   Grand total             = 1075
# 475 cannot be produced from either table alone.
# --------------------------------------------------------------------------- #
CUSTOMERS_CSV = (
    "customer_id,segment\n"
    "1,Premium\n"
    "2,Standard\n"
    "3,Premium\n"
    "4,Standard\n"
).encode("utf-8")

ORDERS_CSV = (
    "order_id,customer_id,amount\n"
    "101,1,100\n"
    "102,2,200\n"
    "103,3,300\n"
    "104,1,50\n"
    "105,4,400\n"
    "106,3,25\n"
).encode("utf-8")

PREMIUM_TOTAL = 475


def _upload(api_client, name, csv_bytes, session_id=None) -> dict:
    files = {"file": (name, csv_bytes, "text/csv")}
    data = {"session_id": session_id} if session_id else None
    r = api_client.post("/datasets", files=files, data=data)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _numbers(data: dict) -> list[float]:
    flat = [v for row in data["result_table"] for v in row.values()]
    return [float(v) for v in flat if isinstance(v, (int, float))]


# --------------------------------------------------------------------------- #
# 1) Happy path — the join yields the hand-computed number (real LLM).
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("_require_ollama")
def test_join_across_two_csvs_matches_hand_computed(api_client):
    orders = _upload(api_client, "orders.csv", ORDERS_CSV)
    session_id = orders["session_id"]
    customers = _upload(api_client, "customers.csv", CUSTOMERS_CSV, session_id)

    # Hand-computed ground truth via an explicit join.
    o = pd.read_csv(pd.io.common.BytesIO(ORDERS_CSV))
    c = pd.read_csv(pd.io.common.BytesIO(CUSTOMERS_CSV))
    merged = o.merge(c, on="customer_id")
    expected = int(merged[merged["segment"] == "Premium"]["amount"].sum())
    assert expected == PREMIUM_TOTAL

    r = api_client.post(
        "/ask",
        json={
            "session_id": session_id,
            "dataset_ids": [orders["dataset_id"], customers["dataset_id"]],
            "question": (
                "Join orders to customers on customer_id. What is the total order "
                "amount for customers in the 'Premium' segment? Return a single number."
            ),
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    nums = _numbers(data)
    answer = data.get("answer_text") or ""
    assert any(abs(n - PREMIUM_TOTAL) < 1e-6 for n in nums) or (
        str(PREMIUM_TOTAL) in answer
    ), f"join answer did not contain {PREMIUM_TOTAL}: {data}"

    # An answer that ignored the join would surface a single-table total
    # (e.g. 1075 grand total) rather than 475 — guard against that mistake.
    assert not (
        any(abs(n - 1075) < 1e-6 for n in nums) and not any(
            abs(n - PREMIUM_TOTAL) < 1e-6 for n in nums
        )
    ), f"answer looks single-table (grand total), not the join: {data}"

    # Audit row records BOTH datasets in scope.
    with create_db_session() as s:
        q = s.get(Query, data["query_id"])
        assert q is not None
        assert q.code
        assert set(q.dataset_ids) == {orders["dataset_id"], customers["dataset_id"]}


# --------------------------------------------------------------------------- #
# 2) Structural / edge — the executor's multi-table form registers every table
#    (no LLM): a join across the tables is possible and df aliases the first.
# --------------------------------------------------------------------------- #
def test_execute_python_multi_table_registration():
    orders = pd.read_csv(pd.io.common.BytesIO(ORDERS_CSV))
    customers = pd.read_csv(pd.io.common.BytesIO(CUSTOMERS_CSV))
    tables = {"orders": orders, "customers": customers}

    # pandas join across the two namespace variables
    code_pd = (
        "m = orders.merge(customers, on='customer_id')\n"
        "result = int(m[m['segment'] == 'Premium']['amount'].sum())"
    )
    out = execute_python(code_pd, tables=tables)
    assert out["exec_error"] is None, out["exec_error"]
    assert out["result_table"] == [{"value": PREMIUM_TOTAL}]

    # DuckDB join across the two registered tables
    code_sql = (
        "result = con.execute("
        "\"SELECT sum(o.amount) AS total FROM orders o "
        "JOIN customers c ON o.customer_id = c.customer_id "
        "WHERE c.segment = 'Premium'\").df()"
    )
    out2 = execute_python(code_sql, tables=tables)
    assert out2["exec_error"] is None, out2["exec_error"]
    assert out2["result_table"][0]["total"] == PREMIUM_TOTAL

    # Back-compat: `df` aliases the FIRST table.
    out3 = execute_python("result = len(df)", tables=tables)
    assert out3["result_table"] == [{"value": len(orders)}]


# --------------------------------------------------------------------------- #
# 3) Error path — a question naming an unknown dataset is rejected 400.
# --------------------------------------------------------------------------- #
def test_ask_unknown_dataset_rejected(api_client):
    orders = _upload(api_client, "orders.csv", ORDERS_CSV)
    r = api_client.post(
        "/ask",
        json={
            "session_id": orders["session_id"],
            "dataset_ids": [orders["dataset_id"], "does-not-exist"],
            "question": "total amount",
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "BAD_REQUEST"
