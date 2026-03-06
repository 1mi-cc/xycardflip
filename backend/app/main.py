from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .errors import BusyStateError
from .services.autotrade import auto_trade_service
from .services.execution_retry import execution_retry_service
from .services.market_monitor import monitor_service
from .services.proxy_resolver import BusinessBanError
from .services.proxy_resolver import rotate_proxy
from .services.supabase_sync import supabase_sync_service
from .routers.auth import router as auth_router
from .routers.health import router as health_router
from .routers.ingest import router as ingest_router
from .routers.monitor import router as monitor_router
from .routers.opportunities import router as opportunities_router
from .routers.listings import router as listings_router
from .routers.execution import router as execution_router
from .routers.execution_retry import router as execution_retry_router
from .routers.trades import router as trades_router
from .routers.autotrade import router as autotrade_router
from .routers.automation import router as automation_router
from .routers.valuation import router as valuation_router
from .routers.vnpy import router as vnpy_router
from .routers.ragflow import router as ragflow_router
from .routers.supabase import router as supabase_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    def _safe_call(fn) -> dict:
        try:
            result = fn()
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:  # pragma: no cover
            return {"error": str(exc)}

    init_db()
    startup_services: dict[str, dict] = {}
    if settings.auto_start_monitor:
        startup_services["monitor"] = _safe_call(monitor_service.start)
    if settings.auto_start_autotrade:
        startup_services["autotrade"] = _safe_call(auto_trade_service.start)
    if settings.auto_start_execution_retry:
        startup_services["execution_retry"] = _safe_call(execution_retry_service.start)
    if settings.auto_start_supabase_sync:
        startup_services["supabase_sync"] = _safe_call(supabase_sync_service.start)
    app.state.startup_services = startup_services

    try:
        yield
    finally:
        shutdown_services = {
            "supabase_sync": _safe_call(supabase_sync_service.stop),
            "execution_retry": _safe_call(execution_retry_service.stop),
            "autotrade": _safe_call(auto_trade_service.stop),
            "monitor": _safe_call(monitor_service.stop),
        }
        app.state.shutdown_services = shutdown_services


def _include_core_routers(app: FastAPI, prefix: str = "") -> None:
    app.include_router(auth_router, prefix=prefix)
    app.include_router(health_router, prefix=prefix)
    app.include_router(ingest_router, prefix=prefix)
    app.include_router(valuation_router, prefix=prefix)
    app.include_router(listings_router, prefix=prefix)
    app.include_router(opportunities_router, prefix=prefix)
    app.include_router(trades_router, prefix=prefix)
    app.include_router(execution_router, prefix=prefix)
    app.include_router(execution_retry_router, prefix=prefix)
    app.include_router(autotrade_router, prefix=prefix)
    app.include_router(automation_router, prefix=prefix)
    app.include_router(monitor_router, prefix=prefix)
    app.include_router(supabase_router, prefix=prefix)
    app.include_router(vnpy_router, prefix=prefix)
    app.include_router(ragflow_router, prefix=prefix)


def _find_frontend_dist() -> Path | None:
    env_path = os.getenv("FRONTEND_DIST", "").strip()
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(__file__).resolve().parents[2] / "dist",
            Path(__file__).resolve().parents[1] / "frontend_dist",
        ]
    )

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "frontend_dist")
        candidates.append(Path(meipass) / "dist")

    for candidate in candidates:
        index_file = candidate / "index.html"
        if index_file.exists():
            return candidate
    return None


def _frontend_index_response(index_path: Path) -> FileResponse:
    response = FileResponse(index_path)
    # Always revalidate HTML entry to avoid stale SPA shell/chunk map after upgrades.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Card flipping MVP API with data ingestion, valuation, opportunity scoring, "
            "and human-approved trade workflow."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.exception_handler(BusinessBanError)
    async def business_ban_exception_handler(_: Request, exc: BusinessBanError) -> JSONResponse:
        if settings.execution_auto_rotate_proxy_on_ban:
            rotate_proxy(reason=f"global_business_ban:{exc.code}", required=False)
        return JSONResponse(
            status_code=503,
            content={
                "detail": str(exc),
                "business_ban_code": exc.code,
                "context": exc.context,
            },
        )

    @app.exception_handler(BusyStateError)
    async def busy_state_exception_handler(_: Request, exc: BusyStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content=exc.to_payload())

    _include_core_routers(app, prefix="")
    _include_core_routers(app, prefix="/card-api")

    frontend_dist = _find_frontend_dist()
    if frontend_dist:
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/")
        def serve_frontend_index() -> FileResponse:
            return _frontend_index_response(frontend_dist / "index.html")

        @app.get("/{full_path:path}")
        def serve_frontend_spa(full_path: str) -> FileResponse:
            requested = (frontend_dist / full_path).resolve()
            try:
                requested.relative_to(frontend_dist.resolve())
            except ValueError:
                return _frontend_index_response(frontend_dist / "index.html")
            if requested.is_file():
                return FileResponse(requested)
            return _frontend_index_response(frontend_dist / "index.html")

    return app


app = create_app()
