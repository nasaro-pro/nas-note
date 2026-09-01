from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from backend.config import settings

ALLOWED_EXT = {".mp3", ".wav", ".m4a", ".mp4"}
AUDIO_EXT = ALLOWED_EXT | {".flac"}


def slugify(title: str) -> str:
    ascii_only = re.sub(r"[^A-Za-z0-9]+", "-", title.strip()).strip("-").lower()
    return (ascii_only[:20] or "item")


def project_root(rel_dir: str) -> Path:
    return settings.data_dir / rel_dir


def original_dir(rel_dir: str) -> Path:
    return project_root(rel_dir) / "original"


def pick_original(rel_dir: str, preferred_name: str | None = None) -> Path | None:
    folder = original_dir(rel_dir)
    if not folder.exists():
        return None
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXT]
    if not files:
        return None
    if preferred_name:
        for p in files:
            if p.name == preferred_name:
                return p
    return sorted(files, key=lambda p: p.stat().st_mtime)[-1]


def chunks_dir(rel_dir: str) -> Path:
    return project_root(rel_dir) / "chunks"


def transcripts_dir(rel_dir: str) -> Path:
    return project_root(rel_dir) / "transcripts"


def work_dir(rel_dir: str) -> Path:
    return project_root(rel_dir) / "work"


def ensure_dirs(rel_dir: str) -> None:
    for p in (
        original_dir(rel_dir),
        chunks_dir(rel_dir),
        transcripts_dir(rel_dir),
        work_dir(rel_dir),
    ):
        p.mkdir(parents=True, exist_ok=True)


def build_rel_dir(project_id: int, date: str, title: str) -> str:
    return f"projects/{date}/{project_id:04d}_{slugify(title)}"


def today_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_video_url(rel_dir: str, url: str) -> None:
    root = project_root(rel_dir)
    meta = read_json(root / "project.json")
    meta["video_url"] = url
    write_json(root / "project.json", meta)
    write_text(root / "video_url.txt", url)


def load_video_url(rel_dir: str, db_value: object = None) -> str:
    if isinstance(db_value, str) and db_value.strip():
        return db_value.strip()
    meta = read_json(project_root(rel_dir) / "project.json")
    stored = meta.get("video_url")
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    return read_text(project_root(rel_dir) / "video_url.txt").strip()


def delete_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def delete_project_files(rel_dir: str) -> None:
    delete_dir(project_root(rel_dir))
    parent = project_root(rel_dir).parent
    if parent.exists() and parent.name[:4].isdigit() and not any(parent.iterdir()):
        parent.rmdir()


KIND_ORDER = {"original": 0, "chunk": 1, "transcript": 2, "full": 3, "summary": 4, "analysis": 5}


def list_saved_files(rel_dir: str) -> list[dict]:
    root = project_root(rel_dir)
    items: list[dict] = []
    if not root.exists():
        return items

    def add(kind: str, path: Path) -> None:
        if path.is_file():
            items.append({"kind": kind, "name": path.name, "size": path.stat().st_size})

    for p in sorted(original_dir(rel_dir).glob("*")):
        add("original", p)
    if chunks_dir(rel_dir).exists():
        for p in sorted(chunks_dir(rel_dir).glob("part_*")):
            add("chunk", p)
    if transcripts_dir(rel_dir).exists():
        for p in sorted(transcripts_dir(rel_dir).glob("*.txt")):
            add("transcript", p)
    add("full", root / "full_transcript.txt")
    add("summary", root / "summary.txt")
    add("analysis", root / "analysis.txt")
    add("analysis", root / "analysis.json")
    items.sort(key=lambda x: (KIND_ORDER.get(x["kind"], 9), x["name"]))
    return items
