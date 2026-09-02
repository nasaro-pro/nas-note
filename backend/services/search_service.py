from __future__ import annotations

import logging
import re

from backend.database import db

log = logging.getLogger("nas-note")


def _snippet(text: str, q: str, radius: int = 40) -> str:
    if not text:
        return ""
    idx = text.lower().find(q.lower())
    if idx < 0:
        return text[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(q) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def _fts_query(q: str) -> str:
    token = re.sub(r"[^\w가-힣]+", " ", q, flags=re.UNICODE).strip()
    if not token:
        return ""
    parts = [p for p in token.split() if p]
    return " ".join(f'"{p}"' for p in parts)


async def search(q: str) -> list[dict]:
    q = q.strip()
    if not q:
        return []
    results: list[dict] = []
    seen: set[tuple[int, str]] = set()

    titles = await db.fetchall(
        "SELECT id, title, status, date FROM projects WHERE title LIKE ? ORDER BY id DESC",
        (f"%{q}%",),
    )
    for row in titles:
        key = (row["id"], "title")
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "project_id": row["id"],
                "title": row["title"],
                "status": row["status"],
                "date": row["date"],
                "snippet": row["title"],
                "source": "title",
            }
        )

    match = _fts_query(q)
    if match:
        try:
            tr = await db.fetchall(
                """
                SELECT t.project_id, p.title, p.status, p.date, t.content
                FROM transcripts_fts f
                JOIN transcripts t ON t.id = f.rowid
                JOIN projects p ON p.id = t.project_id
                WHERE transcripts_fts MATCH ?
                LIMIT 40
                """,
                (match,),
            )
        except Exception as exc:
            log.warning("transcript FTS failed: %s", exc)
            tr = []
        for row in tr:
            key = (row["project_id"], "transcript")
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "project_id": row["project_id"],
                    "title": row["title"],
                    "status": row["status"],
                    "date": row["date"],
                    "snippet": _snippet(row["content"], q),
                    "source": "transcript",
                }
            )
        try:
            an = await db.fetchall(
                """
                SELECT a.project_id, p.title, p.status, p.date,
                       a.overall_summary, a.extracted_info, a.glossary, a.key_points, a.detailed_summary,
                       a.decisions, a.todos, a.important
                FROM analyses_fts f
                JOIN analyses a ON a.id = f.rowid
                JOIN projects p ON p.id = a.project_id
                WHERE analyses_fts MATCH ?
                LIMIT 40
                """,
                (match,),
            )
        except Exception as exc:
            log.warning("analysis FTS failed: %s", exc)
            an = []
        for row in an:
            blob = " ".join(
                str(row.get(k) or "")
                for k in (
                    "overall_summary",
                    "extracted_info",
                    "glossary",
                    "key_points",
                    "detailed_summary",
                    "decisions",
                    "todos",
                    "important",
                )
            )
            key = (row["project_id"], "analysis")
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "project_id": row["project_id"],
                    "title": row["title"],
                    "status": row["status"],
                    "date": row["date"],
                    "snippet": _snippet(blob, q),
                    "source": "analysis",
                }
            )

    if not any(r["source"] != "title" for r in results):
        likes = await db.fetchall(
            """
            SELECT t.project_id, p.title, p.status, p.date, t.content
            FROM transcripts t
            JOIN projects p ON p.id = t.project_id
            WHERE t.content LIKE ?
            LIMIT 40
            """,
            (f"%{q}%",),
        )
        for row in likes:
            key = (row["project_id"], "transcript")
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "project_id": row["project_id"],
                    "title": row["title"],
                    "status": row["status"],
                    "date": row["date"],
                    "snippet": _snippet(row["content"], q),
                    "source": "transcript",
                }
            )
        likes_a = await db.fetchall(
            """
            SELECT a.project_id, p.title, p.status, p.date,
                   a.overall_summary, a.extracted_info, a.glossary, a.key_points, a.detailed_summary,
                   a.decisions, a.todos, a.important
            FROM analyses a
            JOIN projects p ON p.id = a.project_id
            WHERE a.overall_summary LIKE ? OR a.extracted_info LIKE ? OR a.glossary LIKE ?
               OR a.key_points LIKE ? OR a.detailed_summary LIKE ? OR a.decisions LIKE ?
               OR a.todos LIKE ? OR a.important LIKE ?
            LIMIT 40
            """,
            (f"%{q}%",) * 8,
        )
        for row in likes_a:
            blob = " ".join(str(row.get(k) or "") for k in row.keys() if k not in ("project_id", "title", "status", "date"))
            key = (row["project_id"], "analysis")
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "project_id": row["project_id"],
                    "title": row["title"],
                    "status": row["status"],
                    "date": row["date"],
                    "snippet": _snippet(blob, q),
                    "source": "analysis",
                }
            )
    return results
