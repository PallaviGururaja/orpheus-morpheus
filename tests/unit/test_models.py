"""ORM model round-trips against the real PostgreSQL driver."""
from db.models import Session as SessionRow, Dataset, Query
from db.session import create_db_session


def test_session_dataset_query_roundtrip():
    with create_db_session() as s:
        sess = SessionRow(title="Sales analysis")
        s.add(sess)
        s.flush()
        sid = sess.id

        ds = Dataset(
            session_id=sid,
            name="sales.csv",
            source_type="csv",
            storage_path="/tmp/sales.csv",
            row_count=5,
            column_count=3,
            profile={"columns": [{"name": "region"}], "flags": []},
        )
        s.add(ds)
        s.flush()
        did = ds.id

        q = Query(
            session_id=sid,
            dataset_ids=[did],
            question="total revenue?",
            code="result = df['revenue'].sum()",
            result_table=[{"value": 800}],
            verified=True,
            status="completed",
        )
        s.add(q)
        s.flush()
        qid = q.id

    with create_db_session() as s:
        q = s.get(Query, qid)
        assert q is not None
        assert q.dataset_ids == [did]
        assert q.result_table == [{"value": 800}]
        assert q.verified is True
        ds = s.get(Dataset, did)
        assert ds.profile["columns"][0]["name"] == "region"


def test_cascade_delete_session():
    with create_db_session() as s:
        sess = SessionRow(title="temp")
        s.add(sess)
        s.flush()
        sid = sess.id
        s.add(Dataset(session_id=sid, name="x.csv", storage_path="/tmp/x",
                      row_count=1, column_count=1, profile={}))
        s.flush()

    with create_db_session() as s:
        s.delete(s.get(SessionRow, sid))

    with create_db_session() as s:
        remaining = s.query(Dataset).filter(Dataset.session_id == sid).all()
        assert remaining == []
