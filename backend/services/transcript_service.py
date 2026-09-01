from __future__ import annotations

from pathlib import Path

from backend.storage import project_storage as store


def merge_transcripts(rel_dir: str, parts: list[tuple[int, str]]) -> str:
    ordered = sorted(parts, key=lambda x: x[0])
    full = "\n\n".join(text.strip() for _, text in ordered if text.strip())
    dest = store.project_root(rel_dir) / "full_transcript.txt"
    store.write_text(dest, full)
    return full


def save_part(rel_dir: str, index: int, text: str) -> Path:
    path = store.transcripts_dir(rel_dir) / f"part_{index:04d}.txt"
    store.write_text(path, text)
    return path
