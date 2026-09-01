from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from backend.config import settings


def notes_root() -> Path:
    root = Path(settings.notes_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["id"] = data.get("id") or path.stem
    if data.get("date") and not data.get("date_label"):
        try:
            data["date_label"] = _date_label(str(data["date"]))
        except Exception:
            pass
    return data


def list_notes() -> list[dict]:
    items: list[dict] = []
    root = notes_root()
    for path in root.rglob("*.json"):
        try:
            items.append(_read(path))
        except Exception:
            continue
    items.sort(key=lambda n: n.get("updated_at") or n.get("created_at") or "", reverse=True)
    return items


def get_note(note_id: str) -> dict | None:
    for path in notes_root().rglob(f"{note_id}.json"):
        try:
            return _read(path)
        except Exception:
            return None
    return None


def _path_for(note: dict) -> Path:
    day = note.get("date") or _today()
    folder = notes_root() / day
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{note['id']}.json"


def _date_label(day: str) -> str:
    y, m, d = day.split("-")
    return f"{int(y)}년 {int(m)}월 {int(d)}일"


def create_note() -> dict:
    day = _today()
    note = {
        "id": uuid.uuid4().hex[:12],
        "title": "",
        "body": "",
        "date": day,
        "date_label": _date_label(day),
        "created_at": _now(),
        "updated_at": _now(),
    }
    path = _path_for(note)
    path.write_text(json.dumps(note, ensure_ascii=False, indent=2), encoding="utf-8")
    return note


def update_note(note_id: str, title: str | None, body: str | None) -> dict | None:
    current = get_note(note_id)
    if not current:
        return None
    old = _path_for(current)
    if title is not None:
        current["title"] = title
    if body is not None:
        current["body"] = body
    current["updated_at"] = _now()
    current["date"] = current.get("date") or _today()
    current["date_label"] = _date_label(current["date"])
    dest = _path_for(current)
    dest.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    if old != dest and old.exists():
        old.unlink()
    return current


def delete_note(note_id: str) -> bool:
    for path in notes_root().rglob(f"{note_id}.json"):
        path.unlink(missing_ok=True)
        parent = path.parent
        if parent != notes_root() and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
        return True
    return False
