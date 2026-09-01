from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class FFmpegError(Exception):
    pass


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )


def _human_ffmpeg(stderr: str) -> str:
    text = (stderr or "").strip()
    low = text.lower()
    if any(
        s in low
        for s in (
            "no such file",
            "cannot find",
            "error opening",
            "invalid argument",
            "permission denied",
        )
    ):
        return "원본 파일 위치를 찾지 못했습니다."
    return text[:400]


def _ascii_alias(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


@contextmanager
def _ascii_input(src: Path):
    td = Path(tempfile.mkdtemp(prefix="nasnote_"))
    alias = td / f"in{src.suffix.lower() or '.bin'}"
    try:
        _ascii_alias(src, alias)
        yield alias
    finally:
        shutil.rmtree(td, ignore_errors=True)


@contextmanager
def _ascii_pair(src: Path, out_name: str):
    td = Path(tempfile.mkdtemp(prefix="nasnote_"))
    inn = td / f"in{src.suffix.lower() or '.bin'}"
    out = td / out_name
    try:
        _ascii_alias(src, inn)
        yield inn, out, td
    finally:
        shutil.rmtree(td, ignore_errors=True)


def ffmpeg_ok() -> bool:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return False
    a = _run(["ffmpeg", "-version"])
    b = _run(["ffprobe", "-version"])
    return a.returncode == 0 and b.returncode == 0


def probe(path: Path) -> tuple[float, int]:
    with _ascii_input(path) as inn:
        r = _run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(inn),
            ]
        )
    if r.returncode != 0:
        raise FFmpegError(_human_ffmpeg(r.stderr) or "ffprobe failed")
    data = json.loads(r.stdout or "{}")
    duration = float(data.get("format", {}).get("duration") or 0)
    size = int(path.stat().st_size)
    return duration, size


def convert_to_flac(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ascii_pair(src, "out.flac") as (inn, out, _td):
        common = ["ffmpeg", "-y", "-i", str(inn), "-vn", "-ar", "16000", "-ac", "1", "-c:a", "flac"]
        r = _run([*common, "-map", "0:a:0", str(out)])
        if r.returncode != 0 or not out.exists():
            out.unlink(missing_ok=True)
            r = _run([*common, str(out)])
        if r.returncode != 0 or not out.exists():
            raise FFmpegError(_human_ffmpeg(r.stderr) or "영상에서 오디오를 꺼내지 못했습니다")
        shutil.copy2(out, dest)


def cut_segment(src: Path, dest: Path, start: float, duration: float | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ascii_pair(src, "out.flac") as (inn, out, _td):
        args = ["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(inn)]
        if duration is not None:
            args += ["-t", f"{duration:.3f}"]
        args += ["-c:a", "flac", "-ar", "16000", "-ac", "1", str(out)]
        r = _run(args)
        if r.returncode != 0 or not out.exists():
            raise FFmpegError(_human_ffmpeg(r.stderr) or "cut failed")
        shutil.copy2(out, dest)


def segment_by_time(src: Path, dest_dir: Path, target_sec: float) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with _ascii_pair(src, "seg_%04d.flac") as (inn, pattern, td):
        r = _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(inn),
                "-f",
                "segment",
                "-segment_time",
                f"{max(target_sec, 1):.3f}",
                "-reset_timestamps",
                "1",
                "-c:a",
                "flac",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(pattern),
            ]
        )
        if r.returncode != 0:
            raise FFmpegError(_human_ffmpeg(r.stderr) or "segment failed")
        files = _collect_segments(td, dest_dir)
        if files:
            return files
        doubled = td / "seg_%%04d.flac"
        r = _run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(inn),
                "-f",
                "segment",
                "-segment_time",
                f"{max(target_sec, 1):.3f}",
                "-reset_timestamps",
                "1",
                "-c:a",
                "flac",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(doubled),
            ]
        )
        if r.returncode != 0:
            raise FFmpegError(_human_ffmpeg(r.stderr) or "segment failed")
        files = _collect_segments(td, dest_dir)
        if not files:
            raise FFmpegError("구간 파일을 만들지 못했습니다.")
        return files


def _collect_segments(td: Path, dest_dir: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(td.glob("seg_*.flac")):
        if "%" in p.name:
            continue
        dest = dest_dir / p.name
        shutil.copy2(p, dest)
        files.append(dest)
    return files
