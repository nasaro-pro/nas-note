from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config import settings
from backend.database import db
from backend.services.audio_service import ffmpeg_ok, probe
from backend.storage import project_storage as store
from backend.workers.processing_worker import retry_project, worker

router = APIRouter()

ALLOWED = store.ALLOWED_EXT


def _parse_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _percent(status: str, chunks: list[dict]) -> int:
    if status == "pending":
        return 0
    if status == "splitting":
        return 5
    if status == "transcribing":
        total = len(chunks) or 1
        done = sum(1 for c in chunks if c["status"] == "done")
        return 5 + int(80 * done / total)
    if status == "analyzing":
        return 90
    if status == "done":
        return 100
    if status == "failed":
        total = len(chunks) or 1
        done = sum(1 for c in chunks if c["status"] == "done")
        return 5 + int(80 * done / total) if chunks else 5
    return 0


def _live_texts(rel_dir: str) -> tuple[str, str]:
    if not rel_dir:
        return "", ""
    root = store.project_root(rel_dir)
    transcript = store.read_text(root / "full_transcript.txt")
    draft = store.read_text(root / "analysis_draft.txt").strip()
    saved = store.read_text(root / "analysis.txt").strip()
    return transcript, draft or saved


@router.get("/health")
async def health() -> dict:
    ffmpeg = ffmpeg_ok()
    try:
        await db.fetchone("SELECT 1 AS ok")
        db_ok = True
    except Exception:
        db_ok = False
    ok = ffmpeg and db_ok and settings.groq_ready and settings.gemini_ready
    return {
        "status": "ok" if ok else "degraded",
        "ffmpeg": ffmpeg,
        "db": db_ok,
        "groq_key": settings.groq_ready,
        "gemini_key": settings.gemini_ready,
    }


@router.post("/projects", status_code=201)
async def create_project(
    file: UploadFile = File(...),
    title: str | None = Form(None),
) -> dict:
    if not ffmpeg_ok():
        raise HTTPException(503, "FFmpeg가 설치되어 있지 않습니다")
    if not settings.groq_ready:
        raise HTTPException(503, "GROQ_API_KEY가 없습니다")
    if not settings.gemini_ready:
        raise HTTPException(503, "GEMINI_API_KEY가 없습니다")
    raw_name = Path(file.filename or "audio").name
    name = re.sub(r'[<>:"/\\|?*]', "_", raw_name).strip() or "audio"
    if name in {".", ".."}:
        name = "audio"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(400, "MP3, WAV, M4A, MP4만 올릴 수 있습니다.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "파일이 비어 있습니다")

    stem = Path(name).stem
    title = (title or "").strip() or stem
    date = store.today_date()
    project_id = await db.execute(
        """INSERT INTO projects (title, original_filename, date, rel_dir, file_size, status)
           VALUES (?, ?, ?, '', ?, 'pending')""",
        (title, name, date, len(data)),
    )
    rel = store.build_rel_dir(project_id, date, title)
    store.ensure_dirs(rel)
    dest = store.original_dir(rel) / name
    dest.write_bytes(data)
    duration = 0.0
    try:
        duration, size = probe(dest)
    except Exception:
        size = len(data)
    await db.execute(
        "UPDATE projects SET rel_dir=?, duration=?, file_size=?, updated_at=datetime('now') WHERE id=?",
        (rel, duration, size, project_id),
    )
    worker.enqueue(project_id)
    return {"id": project_id, "status": "pending"}


@router.get("/projects")
async def list_projects() -> list[dict]:
    rows = await db.fetchall("SELECT * FROM projects ORDER BY date DESC, id DESC")
    out = []
    for row in rows:
        chunks = await db.fetchall(
            "SELECT chunk_index, status FROM chunks WHERE project_id=? ORDER BY chunk_index",
            (row["id"],),
        )
        out.append(
            {
                **row,
                "chunks": chunks,
                "percent": _percent(row["status"], chunks),
                "files": store.list_saved_files(row["rel_dir"]) if row.get("rel_dir") else [],
            }
        )
    return out


@router.get("/projects/{project_id}")
async def get_project(project_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    chunks = await db.fetchall(
        "SELECT chunk_index, filename, file_size, status, retry_count FROM chunks WHERE project_id=? ORDER BY chunk_index",
        (project_id,),
    )
    analysis_row = await db.fetchone("SELECT * FROM analyses WHERE project_id=?", (project_id,))
    analysis = None
    if analysis_row:
        analysis = {
            "overall_summary": analysis_row["overall_summary"] or "",
            "extracted_info": _parse_list(dict(analysis_row).get("extracted_info")),
            "key_points": _parse_list(analysis_row["key_points"]),
            "detailed_summary": analysis_row["detailed_summary"] or "",
            "decisions": _parse_list(analysis_row["decisions"]),
            "todos": _parse_list(analysis_row["todos"]),
            "important": _parse_list(analysis_row["important"]),
        }
    transcript, analysis_text = _live_texts(row["rel_dir"])
    return {
        **row,
        "video_url": store.load_video_url(row["rel_dir"], row.get("video_url")),
        "chunks": chunks,
        "percent": _percent(row["status"], chunks),
        "analysis": analysis,
        "transcript": transcript,
        "analysis_text": analysis_text,
        "files": store.list_saved_files(row["rel_dir"]) if row.get("rel_dir") else [],
    }


@router.get("/projects/{project_id}/status")
async def project_status(project_id: int) -> dict:
    row = await db.fetchone(
        "SELECT id, status, error_message, rel_dir FROM projects WHERE id=?",
        (project_id,),
    )
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    chunks = await db.fetchall(
        "SELECT chunk_index, file_size, status FROM chunks WHERE project_id=? ORDER BY chunk_index",
        (project_id,),
    )
    transcript, analysis_text = _live_texts(row["rel_dir"])
    return {
        "id": row["id"],
        "status": row["status"],
        "percent": _percent(row["status"], chunks),
        "error_message": row["error_message"],
        "chunks": chunks,
        "transcript": transcript,
        "analysis_text": analysis_text,
    }


@router.get("/projects/{project_id}/transcript")
async def project_transcript(project_id: int) -> dict:
    row = await db.fetchone("SELECT rel_dir FROM projects WHERE id=?", (project_id,))
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    text = store.read_text(store.project_root(row["rel_dir"]) / "full_transcript.txt")
    return {"text": text}


@router.post("/projects/{project_id}/retry")
async def project_retry(project_id: int) -> dict:
    row = await db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    await retry_project(project_id)
    return {"id": project_id, "status": "pending"}


class ProjectPatch(BaseModel):
    video_url: str | None = None


def _normalize_file_addr(raw: str) -> str:
    text = (raw or "").strip().strip('"').strip("'")
    return text


def _as_local_path(raw: str) -> Path | None:
    text = _normalize_file_addr(raw)
    if not text or re.match(r"^https?://", text, re.I):
        return None
    if text.lower().startswith("file:"):
        parsed = urlparse(text)
        path = unquote(parsed.path or "")
        if parsed.netloc:
            path = f"//{parsed.netloc}{path}"
        elif re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
        text = path.replace("/", "\\") if os.name == "nt" else path
    return Path(text) if text else None


@router.patch("/projects/{project_id}")
async def patch_project(project_id: int, body: ProjectPatch) -> dict:
    row = await db.fetchone("SELECT id, rel_dir FROM projects WHERE id=?", (project_id,))
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    url = _normalize_file_addr(body.video_url or "")
    await db.execute(
        "UPDATE projects SET video_url=?, updated_at=datetime('now') WHERE id=?",
        (url, project_id),
    )
    if row.get("rel_dir"):
        store.save_video_url(row["rel_dir"], url)
    return {"id": project_id, "video_url": url}


@router.post("/projects/{project_id}/open-file")
async def open_project_file(project_id: int) -> dict:
    row = await db.fetchone("SELECT rel_dir, video_url FROM projects WHERE id=?", (project_id,))
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    addr = store.load_video_url(row["rel_dir"], row.get("video_url"))
    path = _as_local_path(addr)
    if not path:
        raise HTTPException(400, "저장된 파일 주소가 없습니다.")
    if not path.exists():
        raise HTTPException(404, "그 경로에 파일이 없습니다.")
    target = str(path)
    try:
        if hasattr(os, "startfile"):
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            import subprocess

            opener = "open" if os.uname().sysname == "Darwin" else "xdg-open"
            subprocess.Popen([opener, target])
    except OSError as exc:
        raise HTTPException(400, "파일을 열지 못했습니다.") from exc
    return {"ok": True}


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: int) -> None:
    row = await db.fetchone("SELECT rel_dir FROM projects WHERE id=?", (project_id,))
    if not row:
        raise HTTPException(404, "이 프로젝트를 찾을 수 없습니다.")
    store.delete_project_files(row["rel_dir"])
    await db.execute("DELETE FROM projects WHERE id=?", (project_id,))
