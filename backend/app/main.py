from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers.health import router as health_router
from .routers.ingest import router as ingest_router
from .routers.monitor import router as monitor_router
from .routers.opportunities import router as opportunities_router
from .routers.listings import router as listings_router
from .routers.trades import router as trades_router
from .routers.valuation import router as valuation_router
from .routers.vnpy import router as vnpy_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def _include_core_routers(app: FastAPI, prefix: str = "") -> None:
    app.include_router(health_router, prefix=prefix)
    app.include_router(ingest_router, prefix=prefix)
    app.include_router(valuation_router, prefix=prefix)
    app.include_router(listings_router, prefix=prefix)
    app.include_router(opportunities_router, prefix=prefix)
    app.include_router(trades_router, prefix=prefix)
    app.include_router(monitor_router, prefix=prefix)
    app.include_router(vnpy_router, prefix=prefix)


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

    _include_core_routers(app, prefix="")
    _include_core_routers(app, prefix="/card-api")

    frontend_dist = _find_frontend_dist()
    if frontend_dist:
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/")
        def serve_frontend_index() -> FileResponse:
            return FileResponse(frontend_dist / "index.html")

        @app.get("/{full_path:path}")
        def serve_frontend_spa(full_path: str) -> FileResponse:
            requested = (frontend_dist / full_path).resolve()
            try:
                requested.relative_to(frontend_dist.resolve())
            except ValueError:
                return FileResponse(frontend_dist / "index.html")
            if requested.is_file():
                return FileResponse(requested)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
