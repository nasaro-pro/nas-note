from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.config import settings
from backend.database.db import init_db
from backend.api.projects import router as projects_router
from backend.api.search import router as search_router
from backend.api.notes import router as notes_router
from backend.workers.processing_worker import worker


def _setup_logging() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    logging.getLogger("nas-note").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    await init_db()
    await worker.start()
    yield


app = FastAPI(title="nas-note", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://[::1]:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(projects_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(notes_router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return (
        '<!doctype html><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0;url=http://localhost:5173/">'
        "<p>nas-note 화면은 "
        '<a href="http://localhost:5173/">http://localhost:5173/</a>'
        " 입니다.</p>"
    )
