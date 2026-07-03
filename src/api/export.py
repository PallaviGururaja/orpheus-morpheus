"""CSV export endpoints (Phase 3).

* ``GET /queries/{id}/export`` — download a persisted query's ``result_table``
  as CSV. **No LLM** — byte-for-byte reproducible from the audit row.
* ``GET /dashboards/{id}/widgets/{widget_id}/export`` — recompute one dashboard
  widget's aggregate server-side and stream the rows as CSV (parity with the
  frontend's client-side blob export). **No LLM** — deterministic pandas.

The ``Dashboard`` model + ``aggregate`` helper these depend on are owned by the
``dashboard-backend`` slice; this slice only reads them.
"""
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from analysis.aggregate import (
    AggregationError,
    aggregate,
    load_dataset_dataframe,
)
from api._common import api_error
from db.models import Dashboard, Dataset, Query
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.export")


def _rows_to_csv(rows: list[dict]) -> str:
    """Serialize a list of row dicts to CSV text.

    Header is the union of keys across rows, preserving first-seen order (the
    first row's keys drive the common case). Missing cells are blank; ``None``
    renders as an empty cell.
    """
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {k: ("" if row.get(k) is None else row.get(k)) for k in fieldnames}
        )
    return buffer.getvalue()


@router.get("/queries/{query_id}/export")
def export_query_csv(
    query_id: str, session: Session = Depends(get_session)
) -> Response:
    q = session.get(Query, query_id)
    if q is None:
        raise api_error("NOT_FOUND", f"No such query: {query_id}", 404)

    rows = q.result_table
    if not rows:
        raise api_error(
            "BAD_REQUEST", "Query has no result table to export.", 400
        )

    body = _rows_to_csv(rows)
    _log.info("export.query_csv", query_id=query_id, row_count=len(rows))
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="query-{query_id}.csv"'
        },
    )


def _find_widget(widgets, widget_id: str) -> dict | None:
    for w in widgets or []:
        if isinstance(w, dict) and str(w.get("id")) == str(widget_id):
            return w
    return None


@router.get("/dashboards/{dashboard_id}/widgets/{widget_id}/export")
def export_widget_csv(
    dashboard_id: str,
    widget_id: str,
    session: Session = Depends(get_session),
) -> Response:
    dash = session.get(Dashboard, dashboard_id)
    if dash is None:
        raise api_error("NOT_FOUND", f"No such dashboard: {dashboard_id}", 404)

    widget = _find_widget(dash.widgets, widget_id)
    if widget is None:
        raise api_error("NOT_FOUND", f"No such widget: {widget_id}", 404)

    dataset_id = widget.get("dataset_id")
    ds = session.get(Dataset, dataset_id) if dataset_id else None
    if ds is None:
        raise api_error(
            "BAD_REQUEST",
            "Widget spec no longer valid: its dataset is missing.",
            400,
        )

    try:
        df = load_dataset_dataframe(ds.storage_path)
        result = aggregate(
            df=df,
            profile=ds.profile or {},
            dimensions=widget.get("dimensions") or [],
            measure=widget.get("measure"),
            agg=widget.get("agg", ""),
        )
    except AggregationError as exc:
        raise api_error("BAD_REQUEST", str(exc), 400)
    except Exception as exc:  # noqa: BLE001
        _log.error("export.widget_load_error", dashboard_id=dashboard_id, error=str(exc))
        raise api_error("BAD_REQUEST", f"Could not export widget: {exc}", 400)

    body = _rows_to_csv(result["rows"])
    _log.info(
        "export.widget_csv",
        dashboard_id=dashboard_id,
        widget_id=widget_id,
        row_count=result["row_count"],
    )
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="widget-{widget_id}.csv"'
        },
    )
