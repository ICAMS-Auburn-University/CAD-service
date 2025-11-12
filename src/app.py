import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import init_supabase

from api.routes import router
from dotenv import load_dotenv

import multiprocessing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="CAD Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
multiprocessing.set_start_method("spawn", force=True)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.ico")


@app.on_event("startup")
async def startup_event():
    load_dotenv()
    init_supabase()
