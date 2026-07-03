"""Dashboard builder endpoints (Phase 3 headline). Deterministic — NO LLM.

* ``POST /dashboard/aggregate`` — group-by aggregate one loaded dataset for a
  single widget (pandas over the on-disk file), validated against the profile.
* ``POST/GET/PUT/DELETE /dashboards`` — persist/reload named dashboards.
"""
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from analysis.aggregate import (
    VALID_CHART_TYPES,
    AggregationError,
    aggregate,
    load_dataset_dataframe,
)
from api._common import api_error, ok
from db.models import Dashboard, Dataset, Session as SessionRow
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.dashboard")


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
class AggregateRequest(BaseModel):
    dataset_id: str
    dimensions: list[str] = Field(default_factory=list)
    measure: str | None = None
    agg: str
    chart_type: str


@router.post("/dashboard/aggregate")
def dashboard_aggregate(
    body: AggregateRequest, session: Session = Depends(get_session)
) -> dict:
    if body.chart_type not in VALID_CHART_TYPES:
        raise api_error(
            "BAD_REQUEST",
            f"Unknown chart_type '{body.chart_type}'. Must be one of "
            f"{sorted(VALID_CHART_TYPES)}.",
            400,
        )

    ds = session.get(Dataset, body.dataset_id)
    if ds is None:
        raise api_error("NOT_FOUND", f"No such dataset: {body.dataset_id}", 404)

    try:
        df = load_dataset_dataframe(ds.storage_path)
    except Exception as exc:  # noqa: BLE001
        _log.error("dashboard.load_error", dataset_id=body.dataset_id, error=str(exc))
        raise api_error("BAD_REQUEST", f"Could not load dataset: {exc}", 400)

    try:
        result = aggregate(
            df=df,
            profile=ds.profile or {},
            dimensions=body.dimensions,
            measure=body.measure,
            agg=body.agg,
        )
    except AggregationError as exc:
        raise api_error("BAD_REQUEST", str(exc), 400)

    _log.info(
        "dashboard.aggregated",
        dataset_id=body.dataset_id,
        agg=body.agg,
        dimensions=body.dimensions,
        rows=result["row_count"],
        truncated=result["truncated"],
    )

    return ok(
        {
            "columns": result["columns"],
            "rows": result["rows"],
            "agg": body.agg,
            "measure": body.measure,
            "dimensions": body.dimensions,
            "chart_type": body.chart_type,
            "row_count": result["row_count"],
            "truncated": result["truncated"],
        }
    )


# --------------------------------------------------------------------------- #
# Dashboard CRUD
# --------------------------------------------------------------------------- #
class DashboardCreate(BaseModel):
    session_id: str
    name: str
    widgets: list[Any] = Field(default_factory=list)


class DashboardUpdate(BaseModel):
    name: str | None = None
    widgets: list[Any] | None = None


def _dashboard_to_dict(d: Dashboard) -> dict:
    return {
        "id": d.id,
        "session_id": d.session_id,
        "name": d.name,
        "widgets": d.widgets,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _validate_widgets(widgets: Any) -> list:
    if not isinstance(widgets, list):
        raise api_error("BAD_REQUEST", "`widgets` must be a list.", 400)
    for w in widgets:
        if not isinstance(w, dict):
            raise api_error("BAD_REQUEST", "Each widget must be an object.", 400)
    return widgets


@router.post("/dashboards")
def create_dashboard(
    body: DashboardCreate, session: Session = Depends(get_session)
) -> dict:
    if not body.name or not body.name.strip():
        raise api_error("BAD_REQUEST", "Dashboard name is required.", 400)
    widgets = _validate_widgets(body.widgets)

    sess = session.get(SessionRow, body.session_id)
    if sess is None:
        raise api_error("NOT_FOUND", f"No such session: {body.session_id}", 404)

    dash = Dashboard(session_id=body.session_id, name=body.name, widgets=widgets)
    session.add(dash)
    session.flush()
    _log.info("dashboard.created", dashboard_id=dash.id, session_id=body.session_id)
    return ok(_dashboard_to_dict(dash))


@router.get("/dashboards")
def list_dashboards(
    session_id: str | None = None, session: Session = Depends(get_session)
) -> dict:
    q = session.query(Dashboard)
    if session_id:
        q = q.filter(Dashboard.session_id == session_id)
    rows = q.order_by(Dashboard.created_at.desc()).all()
    return ok(
        {
            "dashboards": [
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "name": r.name,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        }
    )


@router.get("/dashboards/{dashboard_id}")
def get_dashboard(
    dashboard_id: str, session: Session = Depends(get_session)
) -> dict:
    d = session.get(Dashboard, dashboard_id)
    if d is None:
        raise api_error("NOT_FOUND", f"No such dashboard: {dashboard_id}", 404)
    return ok(_dashboard_to_dict(d))


@router.put("/dashboards/{dashboard_id}")
def update_dashboard(
    dashboard_id: str,
    body: DashboardUpdate,
    session: Session = Depends(get_session),
) -> dict:
    d = session.get(Dashboard, dashboard_id)
    if d is None:
        raise api_error("NOT_FOUND", f"No such dashboard: {dashboard_id}", 404)
    if body.name is not None:
        if not body.name.strip():
            raise api_error("BAD_REQUEST", "Dashboard name cannot be empty.", 400)
        d.name = body.name
    if body.widgets is not None:
        d.widgets = _validate_widgets(body.widgets)
    session.flush()
    _log.info("dashboard.updated", dashboard_id=dashboard_id)
    return ok(_dashboard_to_dict(d))


@router.delete("/dashboards/{dashboard_id}")
def delete_dashboard(
    dashboard_id: str, session: Session = Depends(get_session)
) -> dict:
    d = session.get(Dashboard, dashboard_id)
    if d is None:
        raise api_error("NOT_FOUND", f"No such dashboard: {dashboard_id}", 404)
    session.delete(d)
    _log.info("dashboard.deleted", dashboard_id=dashboard_id)
    return ok({"deleted": True})
