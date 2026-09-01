from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from backend.config import settings
from backend.services import audio_service as audio

MAX = settings.max_chunk_bytes
MAX_SEC = settings.max_chunk_seconds
SAFETY = settings.split_safety_ratio


class SplitError(Exception):
    pass


def _copy_in(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _place(src: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dest.resolve():
        return dest
    if dest.exists():
        dest.unlink()
    try:
        os.replace(src, dest)
    except OSError:
        shutil.copy2(src, dest)
        src.unlink(missing_ok=True)
    if not dest.exists():
        raise SplitError("나눈 파일을 옮기지 못했습니다.")
    return dest


def _rename_sequential(files: list[Path], dest_dir: Path) -> list[Path]:
    out: list[Path] = []
    for i, src in enumerate(files, start=1):
        dest = dest_dir / f"part_{i:04d}.flac"
        out.append(_place(src, dest))
    return out


def _split_in_half(src: Path, dest_dir: Path, seq: list[int]) -> list[Path]:
    duration, _ = audio.probe(src)
    half = max(duration / 2, 0.5)
    seq[0] += 1
    a = dest_dir / f"h{seq[0]:04d}a.flac"
    seq[0] += 1
    b = dest_dir / f"h{seq[0]:04d}b.flac"
    audio.cut_segment(src, a, 0, half)
    audio.cut_segment(src, b, half, None)
    src.unlink(missing_ok=True)
    return [a, b]


def _ensure_under_limit(chunk: Path, dest_dir: Path, depth: int, seq: list[int]) -> list[Path]:
    duration, size = audio.probe(chunk)
    if size <= MAX and duration <= MAX_SEC:
        return [chunk]
    if depth >= 8:
        raise SplitError(f"조각을 더 나눌 수 없습니다: {chunk.name}")
    if duration <= 0:
        raise SplitError("길이를 읽을 수 없습니다")
    bytes_per_sec = size / duration
    target_by_size = (MAX / bytes_per_sec) * SAFETY
    target_sec = max(min(target_by_size, MAX_SEC), 1.0)
    tmp = dest_dir / f"re{depth}_{seq[0]:04d}"
    seq[0] += 1
    tmp.mkdir(exist_ok=True)
    parts = audio.segment_by_time(chunk, tmp, target_sec)
    chunk.unlink(missing_ok=True)
    result: list[Path] = []
    for p in parts:
        seq[0] += 1
        moved = dest_dir / f"c{depth}_{seq[0]:04d}.flac"
        _place(p, moved)
        result.extend(_ensure_under_limit(moved, dest_dir, depth + 1, seq))
    shutil.rmtree(tmp, ignore_errors=True)
    return result


def split_audio(original: Path, chunks_dir: Path) -> list[Path]:
    if chunks_dir.exists():
        shutil.rmtree(chunks_dir, ignore_errors=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="nasnote_split_"))
    seq = [0]
    try:
        inn = work / f"src{original.suffix.lower() or '.bin'}"
        _copy_in(original, inn)
        full = work / "full.flac"
        audio.convert_to_flac(inn, full)
        inn.unlink(missing_ok=True)
        size = full.stat().st_size
        duration, _ = audio.probe(full)

        if duration <= 0:
            raise SplitError("원본 길이를 읽을 수 없습니다")

        if size <= MAX and duration <= MAX_SEC:
            dest = chunks_dir / "part_0001.flac"
            _copy_in(full, dest)
            return [dest]

        bytes_per_sec = size / max(duration, 0.001)
        target_by_size = (MAX / bytes_per_sec) * SAFETY
        target_sec = max(min(target_by_size, MAX_SEC), 1.0)
        raw = audio.segment_by_time(full, work, target_sec)
        full.unlink(missing_ok=True)

        pieces: list[Path] = []
        for p in raw:
            seq[0] += 1
            moved = work / f"p{seq[0]:04d}.flac"
            _place(p, moved)
            pieces.extend(_ensure_under_limit(moved, work, 0, seq))

        if pieces:
            last = pieces[-1]
            last_size = last.stat().st_size
            if MAX < last_size < 2 * MAX:
                halves = _split_in_half(last, work, seq)
                pieces[-1:] = halves

        missing = [p.name for p in pieces if not p.exists()]
        if missing:
            raise SplitError("나눈 파일이 임시 폴더에서 사라졌습니다.")

        for p in pieces:
            if p.stat().st_size > MAX:
                raise SplitError(f"분할 후에도 24MB를 넘습니다: {p.name} ({p.stat().st_size})")

        named = _rename_sequential(pieces, work)
        out: list[Path] = []
        for src in named:
            dest = chunks_dir / src.name
            _copy_in(src, dest)
            out.append(dest)
        if not out:
            raise SplitError("분할 결과가 비어 있습니다.")
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)
