from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from backend.config import settings

ALLOWED_EXT = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".webm",
    ".ogg",
    ".weba",
    ".flac",
    ".mov",
    ".mkv",
    ".aac",
    ".mpeg",
    ".mpg",
    ".mpga",
    ".3gp",
}
AUDIO_EXT = ALLOWED_EXT
MIME_EXT = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/flac": ".flac",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "audio/webm;codecs=opus": ".webm",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
    "video/3gpp": ".3gp",
    "video/mpeg": ".mpeg",
}


def guess_ext(filename: str, content_type: str | None, head: bytes) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in ALLOWED_EXT:
        return ext
    ct = (content_type or "").split(";")[0].strip().lower()
    mapped = MIME_EXT.get(ct)
    if mapped:
        return mapped
    if head.startswith(b"ID3") or (len(head) > 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return ".mp3"
    if head.startswith(b"RIFF") and b"WAVE" in head[:16]:
        return ".wav"
    if head.startswith(b"OggS"):
        return ".ogg"
    if head.startswith(b"fLaC"):
        return ".flac"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return ".webm"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in {b"qt  ", b"M4V ", b"mqt "}:
            return ".mov"
        if brand.startswith(b"M4A"):
            return ".m4a"
        return ".mp4"
    return ext


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
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    last: OSError | None = None
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except OSError as exc:
            last = exc
            time.sleep(0.04)
    if last:
        raise last


def read_text(path: Path) -> str:
    for _ in range(4):
        try:
            if not path.exists():
                return ""
            return path.read_text(encoding="utf-8")
        except OSError:
            time.sleep(0.03)
    return ""


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
