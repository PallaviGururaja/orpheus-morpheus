"""In-app local file browser + load-by-path.

The OS file-picker dialog can be unreliable on some Windows setups (it opens to
a folder with nothing shown). Since this is a single-user *local* tool, we let
the app browse the user's own files server-side and load a CSV by path — no OS
dialog involved. All access is confined to the user's home directory.
"""
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from analysis.engine import (
    ACCEPTED_EXTS,
    load_dataframe,
    source_type_for,
    store_upload,
)
from analysis.profiler import profile_dataframe
from api._common import ok, api_error
from db.models import Dataset, Session as SessionRow
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.local_files")


def _home() -> Path:
    return Path.home().resolve()


def _within_home(p: Path) -> bool:
    try:
        p.resolve().relative_to(_home())
        return True
    except (ValueError, OSError):
        return False


def _shortcuts() -> list[dict]:
    home = _home()
    out = [{"label": "Home", "path": str(home)}]
    for name in ("Downloads", "Documents", "Desktop"):
        d = home / name
        if d.is_dir():
            out.append({"label": name, "path": str(d)})
    return out


@router.get("/local/browse")
def browse(path: str | None = None) -> dict:
    """List sub-folders and CSV files under a directory (home-confined)."""
    target = Path(path).resolve() if path else _home()
    if not _within_home(target):
        raise api_error("FORBIDDEN", "Access is limited to your home folder.", 403)
    if not target.is_dir():
        raise api_error("BAD_REQUEST", "Not a folder.", 400)

    dirs: list[dict] = []
    files: list[dict] = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: e.name.lower()):
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir():
                    dirs.append({"name": entry.name, "path": str(entry)})
                elif entry.suffix.lower() in ACCEPTED_EXTS:
                    files.append(
                        {"name": entry.name, "path": str(entry), "size": entry.stat().st_size}
                    )
            except OSError:
                continue
    except PermissionError:
        raise api_error("FORBIDDEN", "You don't have permission to open that folder.", 403)

    parent = str(target.parent) if _within_home(target.parent) and target != _home() else None
    return ok(
        {
            "cwd": str(target),
            "parent": parent,
            "shortcuts": _shortcuts(),
            "dirs": dirs,
            "files": files,
        }
    )


class LoadLocalRequest(BaseModel):
    path: str
    session_id: str | None = None
    sheet: str | None = None


@router.post("/datasets/local")
def load_local(body: LoadLocalRequest, session: Session = Depends(get_session)) -> dict:
    """Load a CSV already on disk (chosen via the in-app browser) as a dataset."""
    src = Path(body.path).resolve()
    if not _within_home(src):
        raise api_error("FORBIDDEN", "Access is limited to your home folder.", 403)
    if not src.is_file() or src.suffix.lower() not in ACCEPTED_EXTS:
        raise api_error("BAD_REQUEST", "Please choose a .csv or .xlsx file.", 400)

    try:
        content = src.read_bytes()
    except OSError as exc:
        raise api_error("BAD_REQUEST", f"Could not read file: {exc}", 400)
    if not content:
        raise api_error("BAD_REQUEST", "That file is empty.", 400)

    filename = src.name
    if body.session_id:
        sess = session.get(SessionRow, body.session_id)
        if sess is None:
            sess = SessionRow(id=body.session_id, title=filename)
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
        df = load_dataframe(storage_path, body.sheet)
    except pd.errors.EmptyDataError:
        raise api_error("BAD_REQUEST", "File has no parseable data.", 400)
    except ValueError as exc:
        raise api_error("BAD_REQUEST", f"Could not read the file: {exc}", 400)
    except Exception as exc:  # noqa: BLE001
        _log.error("local.parse_error", error=str(exc))
        raise api_error("BAD_REQUEST", f"Could not parse file: {exc}", 400)

    profile = profile_dataframe(df)
    session.add(
        Dataset(
            id=dataset_id,
            session_id=session_id,
            name=filename,
            source_type=source_type_for(filename),
            storage_path=storage_path,
            row_count=profile["row_count"],
            column_count=profile["column_count"],
            profile=profile,
            is_derived=False,
        )
    )
    _log.info(
        "local.loaded",
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
