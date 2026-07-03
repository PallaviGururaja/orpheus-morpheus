"""CSV upload + profile endpoint."""
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from analysis.engine import load_csv, store_upload
from analysis.profiler import profile_dataframe
from api._common import ok, api_error
from db.models import Dataset, Session as SessionRow
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.datasets")


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    filename = file.filename or "dataset.csv"
    if not filename.lower().endswith(".csv"):
        raise api_error("BAD_REQUEST", "Only CSV files are supported in Phase 1.", 400)

    content = await file.read()
    if not content:
        raise api_error("BAD_REQUEST", "Uploaded file is empty.", 400)

    # Ensure a session exists.
    if session_id:
        sess = session.get(SessionRow, session_id)
        if sess is None:
            sess = SessionRow(id=session_id, title=filename)
            session.add(sess)
            session.flush()
    else:
        sess = SessionRow(title=filename)
        session.add(sess)
        session.flush()
    session_id = sess.id

    dataset_id = str(uuid4())
    try:
        storage_path = store_upload(dataset_id, filename, content)
        df = load_csv(storage_path)
    except pd.errors.EmptyDataError:
        raise api_error("BAD_REQUEST", "CSV file has no parseable data.", 400)
    except Exception as exc:  # noqa: BLE001
        _log.error("datasets.parse_error", error=str(exc))
        raise api_error("BAD_REQUEST", f"Could not parse CSV: {exc}", 400)

    profile = profile_dataframe(df)

    ds = Dataset(
        id=dataset_id,
        session_id=session_id,
        name=filename,
        source_type="csv",
        storage_path=storage_path,
        row_count=profile["row_count"],
        column_count=profile["column_count"],
        profile=profile,
        is_derived=False,
    )
    session.add(ds)

    _log.info(
        "datasets.uploaded",
        session_id=session_id,
        dataset_id=dataset_id,
        rows=profile["row_count"],
        cols=profile["column_count"],
    )

    return ok(
        {
            "session_id": session_id,
            "dataset_id": dataset_id,
            "name": filename,
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
            "profile": profile,
        }
    )
