from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from backend.config import settings
from backend.database import db
from backend.services import gemini_service, splitter_service, stt_service, transcript_service
from backend.services.audio_service import probe
from backend.storage import project_storage as store

log = logging.getLogger("nas-note")

ACTIVE = {"pending", "splitting", "transcribing", "analyzing"}


class ProcessingWorker:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self._queued: set[int] = set()
        self.current: int | None = None
        self._task: asyncio.Task | None = None

    def enqueue(self, project_id: int) -> None:
        if project_id == self.current or project_id in self._queued:
            return
        self._queued.add(project_id)
        self.queue.put_nowait(project_id)

    async def start(self) -> None:
        await db.execute(
            "UPDATE chunks SET status='pending' WHERE status='processing'"
        )
        rows = await db.fetchall(
            f"SELECT id FROM projects WHERE status IN ({','.join('?' * len(ACTIVE))}) ORDER BY created_at",
            tuple(ACTIVE),
        )
        for row in rows:
            self.enqueue(row["id"])
        self._task = asyncio.create_task(self._loop(), name="nas-note-worker")

    async def _loop(self) -> None:
        while True:
            project_id = await self.queue.get()
            self._queued.discard(project_id)
            self.current = project_id
            try:
                await process_project(project_id)
            except Exception:
                log.exception("project %s failed", project_id)
                await _fail(project_id, "처리 중 오류가 발생했습니다.")
            finally:
                self.current = None
                self.queue.task_done()


worker = ProcessingWorker()


async def _touch(project_id: int, **fields: object) -> None:
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    await db.execute(
        f"UPDATE projects SET {sets}, updated_at=datetime('now') WHERE id=?",
        tuple(fields.values()) + (project_id,),
    )


async def _fail(project_id: int, message: str) -> None:
    await _touch(project_id, status="failed", error_message=message)


async def _write_project_json(row: dict) -> None:
    root = store.project_root(row["rel_dir"])
    store.write_json(
        root / "project.json",
        {
            "id": row["id"],
            "title": row["title"],
            "date": row["date"],
            "status": row["status"],
            "original_filename": row["original_filename"],
            "video_url": row.get("video_url") or "",
        },
    )


async def _save_analysis(project_id: int, result: gemini_service.AnalysisResult) -> None:
    extracted = db.dumps(result.extracted_info)
    points = db.dumps(result.key_points)
    glossary = db.dumps(result.glossary)
    decisions = db.dumps(result.decisions)
    todos = db.dumps(result.todos)
    important = db.dumps(result.important)
    existing = await db.fetchone("SELECT id FROM analyses WHERE project_id=?", (project_id,))
    if existing:
        await db.execute(
            """UPDATE analyses SET overall_summary=?, extracted_info=?, glossary=?, key_points=?,
               detailed_summary=?, decisions=?, todos=?, important=? WHERE project_id=?""",
            (
                result.overall_summary,
                extracted,
                glossary,
                points,
                result.detailed_summary,
                decisions,
                todos,
                important,
                project_id,
            ),
        )
    else:
        await db.execute(
            """INSERT INTO analyses
               (project_id, overall_summary, extracted_info, glossary, key_points, detailed_summary,
                decisions, todos, important)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                result.overall_summary,
                extracted,
                glossary,
                points,
                result.detailed_summary,
                decisions,
                todos,
                important,
            ),
        )


async def _upsert_transcript(project_id: int, rel: str, index: int, text: str) -> None:
    transcript_service.save_part(rel, index, text)
    existing = await db.fetchone(
        "SELECT id FROM transcripts WHERE project_id=? AND chunk_index=?",
        (project_id, index),
    )
    if existing:
        await db.execute("UPDATE transcripts SET content=? WHERE id=?", (text, existing["id"]))
    else:
        await db.execute(
            "INSERT INTO transcripts (project_id, chunk_index, content) VALUES (?, ?, ?)",
            (project_id, index, text),
        )


async def _transcribe_one(project_id: int, chunk: dict, path: Path, rel: str) -> None:
    await db.execute(
        "UPDATE chunks SET status='processing', error_message=NULL WHERE id=?",
        (chunk["id"],),
    )
    try:
        text = await stt_service.transcribe_chunk(path)
    except Exception as exc:
        await db.execute(
            "UPDATE chunks SET status='failed', retry_count=?, error_message=? WHERE id=?",
            (max(chunk["retry_count"], 3), str(exc)[:300], chunk["id"]),
        )
        raise
    await _upsert_transcript(project_id, rel, chunk["chunk_index"], text)
    await db.execute(
        "UPDATE chunks SET status='done', retry_count=0 WHERE id=?",
        (chunk["id"],),
    )


async def _merge_from_db(project_id: int, rel: str) -> str:
    parts = await db.fetchall(
        "SELECT chunk_index, content FROM transcripts WHERE project_id=? ORDER BY chunk_index",
        (project_id,),
    )
    return transcript_service.merge_transcripts(
        rel, [(p["chunk_index"], p["content"]) for p in parts]
    )


async def process_project(project_id: int) -> None:
    row = await db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not row or row["status"] == "done":
        return

    originals = store.pick_original(row["rel_dir"], row["original_filename"])
    if not originals:
        await _fail(project_id, "원본 파일이 없습니다.")
        return
    original = originals
    rel = row["rel_dir"]
    status = row["status"]

    try:
        duration, size = await asyncio.to_thread(probe, original)
    except Exception:
        duration, size = 0.0, original.stat().st_size
    await _touch(project_id, duration=duration, file_size=size)

    if not settings.groq_ready:
        await _fail(project_id, "GROQ_API_KEY가 없습니다.")
        return

    full = store.read_text(store.project_root(rel) / "full_transcript.txt").strip()
    if status == "failed":
        if full:
            status = "analyzing"
            await _touch(project_id, status="analyzing", error_message=None)
        else:
            status = "pending"
            await _touch(project_id, status="pending", error_message=None)

    need_stt = status in ("pending", "splitting", "transcribing") or not full
    if status == "analyzing":
        need_stt = not full

    if need_stt:
        small = original.stat().st_size <= settings.max_chunk_bytes
        if small:
            await _touch(project_id, status="transcribing", error_message=None)
            existing_chunk = await db.fetchone(
                "SELECT * FROM chunks WHERE project_id=? AND chunk_index=1",
                (project_id,),
            )
            if not existing_chunk:
                await db.execute("DELETE FROM chunks WHERE project_id=?", (project_id,))
                await db.execute(
                    """INSERT INTO chunks (project_id, chunk_index, filename, file_size, status)
                       VALUES (?, 1, ?, ?, 'pending')""",
                    (project_id, original.name, original.stat().st_size),
                )
                existing_chunk = await db.fetchone(
                    "SELECT * FROM chunks WHERE project_id=? AND chunk_index=1",
                    (project_id,),
                )
            if existing_chunk and existing_chunk["status"] != "done":
                try:
                    await _transcribe_one(project_id, existing_chunk, original, rel)
                    await _merge_from_db(project_id, rel)
                except Exception:
                    await _fail(project_id, "Part 0001 전사에 실패했습니다.")
                    return
        else:
            await _touch(project_id, status="splitting", error_message=None)
            try:
                files = await asyncio.to_thread(
                    splitter_service.split_audio, original, store.chunks_dir(rel)
                )
            except Exception as exc:
                log.warning("split failed: %s", exc)
                await _fail(project_id, "분할에 실패했습니다. 다시 시도해 주세요.")
                return
            await db.execute("DELETE FROM chunks WHERE project_id=?", (project_id,))
            await db.execute("DELETE FROM transcripts WHERE project_id=?", (project_id,))
            for i, path in enumerate(files, start=1):
                await db.execute(
                    """INSERT INTO chunks (project_id, chunk_index, filename, file_size, status)
                       VALUES (?, ?, ?, ?, 'pending')""",
                    (project_id, i, path.name, path.stat().st_size),
                )
            await _touch(project_id, status="transcribing")
            chunks = await db.fetchall(
                "SELECT * FROM chunks WHERE project_id=? ORDER BY chunk_index",
                (project_id,),
            )
            for chunk in chunks:
                if chunk["status"] == "done":
                    continue
                path = store.chunks_dir(rel) / chunk["filename"]
                try:
                    await _transcribe_one(project_id, chunk, path, rel)
                    await _merge_from_db(project_id, rel)
                except Exception:
                    await _fail(project_id, f"Part {chunk['chunk_index']:04d} 전사에 실패했습니다.")
                    return

        full = await _merge_from_db(project_id, rel)
        await _touch(project_id, status="analyzing")
        status = "analyzing"

    if status == "analyzing":
        if not settings.gemini_ready:
            await _fail(project_id, "분석에 실패했습니다. 텍스트는 저장되어 있습니다.")
            return
        full = store.read_text(store.project_root(rel) / "full_transcript.txt").strip()
        if not full:
            full = (await _merge_from_db(project_id, rel)).strip()
        if not full:
            await _fail(project_id, "분석에 실패했습니다. 텍스트가 없습니다.")
            return
        row = await db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
        try:
            result = await gemini_service.analyze(row["title"], full, rel)
        except Exception as exc:
            log.warning("gemini failed: %s", exc)
            await _fail(project_id, "분석에 실패했습니다. 텍스트는 저장되어 있습니다.")
            return
        await _save_analysis(project_id, result)
        store.delete_dir(store.work_dir(rel))
        await _touch(project_id, status="done", error_message=None)

    row = await db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if row:
        await _write_project_json(row)


async def retry_project(project_id: int) -> None:
    row = await db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
    if not row:
        return
    full = store.read_text(store.project_root(row["rel_dir"]) / "full_transcript.txt").strip()
    if full:
        await _touch(project_id, status="analyzing", error_message=None)
    else:
        await _touch(project_id, status="pending", error_message=None)
    worker.enqueue(project_id)
