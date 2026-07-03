from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Schema is managed by Alembic (`uv run alembic upgrade head`), not auto-create.
    from config.settings import get_settings
    from observability.events import configure_logging
    configure_logging(get_settings().log_level)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Data Analyst Agent", version="0.1.0", lifespan=_lifespan)
    from api import (
        health, datasets, ask, audit, stubs, local_files, rerun, followups,
        export, dashboard, sessions,
    )
    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(local_files.router)
    app.include_router(ask.router)
    app.include_router(rerun.router)
    app.include_router(followups.router)
    app.include_router(export.router)
    app.include_router(dashboard.router)
    app.include_router(sessions.router)
    app.include_router(audit.router)
    app.include_router(stubs.router)

    import time as _time
    from observability.events import get_logger
    _req_log = get_logger("api.request")

    @app.middleware("http")
    async def _log_requests(request, call_next):
        start = _time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((_time.perf_counter() - start) * 1000)
        _req_log.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        return response

    # Serve the built Next.js static export at /app
    # Run `cd frontend && pnpm build` to generate frontend/out/ before starting.
    # Server starts fine without it (API-only mode when out/ doesn't exist).
    # __file__ = src/api/__init__.py → 3 parents up = repo root
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_out), html=True), name="frontend")

    return app


app = create_app()
