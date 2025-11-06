from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_settings
from api.routes import router


def configure_logging() -> None:
    """Configure root logging for the service."""

    level_name = os.environ.get("CAD_SERVICE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):  # pragma: no cover - simple startup/shutdown hook
    logger.info("CAD Service lifespan starting")
    # Validate configuration on startup; raises if required env vars are missing.
    get_settings()
    yield
    logger.info("CAD Service lifespan shutting down")


app = FastAPI(title="CAD Service", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:  # pragma: no cover - optional asset folder
    logger.warning("Static directory missing at %s", static_dir)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve the favicon for browsers hitting the root endpoint."""

    icon_path = static_dir / "favicon.ico"
    if not icon_path.exists():
        raise HTTPException(status_code=404, detail="Favicon not configured.")
    return FileResponse(icon_path)


app.include_router(router, prefix="/api")


def run() -> None:  # pragma: no cover - exercised via container runtime
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")


__all__ = ["app", "run"]
