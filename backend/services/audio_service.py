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

_ffmpeg_ok_cache: bool | None = None
_ffmpeg_bin: str | None = None
_ffprobe_bin: str | None = None


class FFmpegError(Exception):
    pass


def _exe_name(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _stamp_dir() -> Path | None:
    raw = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME")
    if not raw:
        return None
    return Path(raw) / "nas-note"


def _from_env(name: str) -> list[Path]:
    keys = {
        "ffmpeg": ("NAS_NOTE_FFMPEG", "FFMPEG_BINARY", "FFMPEG_PATH"),
        "ffprobe": ("NAS_NOTE_FFPROBE", "FFPROBE_BINARY", "FFPROBE_PATH"),
    }
    out: list[Path] = []
    for key in keys.get(name, ()):
        raw = (os.environ.get(key) or "").strip().strip('"')
        if not raw:
            continue
        p = Path(raw)
        if p.is_file():
            out.append(p)
            if name == "ffprobe" and p.stem.lower().startswith("ffmpeg"):
                sibling = p.with_name(_exe_name("ffprobe"))
                if sibling.exists():
                    out.append(sibling)
            continue
        if p.is_dir():
            cand = p / _exe_name(name)
            if cand.exists():
                out.append(cand)
    return out


def _common_bins(name: str) -> list[Path]:
    exe = _exe_name(name)
    dirs: list[Path] = []
    stamp = _stamp_dir()
    if stamp:
        marker = stamp / "ffmpeg-path.txt"
        if marker.is_file():
            try:
                line = marker.read_text(encoding="utf-8").strip().strip('"')
            except OSError:
                line = ""
            if line:
                p = Path(line)
                dirs.append(p.parent if p.is_file() else p)
        dirs.append(stamp)
    dirs.extend(
        [
            Path(r"C:\ffmpeg\bin"),
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ffmpeg" / "bin",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "ffmpeg" / "bin",
            Path("/usr/bin"),
            Path("/usr/local/bin"),
            Path("/opt/homebrew/bin"),
        ]
    )
    out = [d / exe for d in dirs]
    which = shutil.which(name)
    if which:
        out.insert(0, Path(which))
    winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget.is_dir():
        try:
            for pkg in winget.glob("Gyan.FFmpeg*"):
                hits = list(pkg.rglob(exe))
                if hits:
                    out.append(hits[0])
                    break
        except OSError:
            pass
    return out


def _works(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        r = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=8,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _resolve(name: str) -> str | None:
    seen: set[str] = set()
    for cand in [*_from_env(name), *_common_bins(name)]:
        key = str(cand).lower()
        if key in seen:
            continue
        seen.add(key)
        if _works(cand):
            return str(cand)
    return None


def ffmpeg_bin() -> str | None:
    global _ffmpeg_bin
    if _ffmpeg_bin:
        return _ffmpeg_bin
    _ffmpeg_bin = _resolve("ffmpeg")
    if _ffmpeg_bin:
        ffdir = str(Path(_ffmpeg_bin).parent)
        os.environ["PATH"] = ffdir + os.pathsep + os.environ.get("PATH", "")
        os.environ["NAS_NOTE_FFMPEG"] = _ffmpeg_bin
    return _ffmpeg_bin


def ffprobe_bin() -> str | None:
    global _ffprobe_bin
    if _ffprobe_bin:
        return _ffprobe_bin
    ff = ffmpeg_bin()
    if ff:
        sibling = Path(ff).with_name(_exe_name("ffprobe"))
        if _works(sibling):
            _ffprobe_bin = str(sibling)
            os.environ["NAS_NOTE_FFPROBE"] = _ffprobe_bin
            return _ffprobe_bin
    _ffprobe_bin = _resolve("ffprobe")
    if _ffprobe_bin:
        os.environ["NAS_NOTE_FFPROBE"] = _ffprobe_bin
    return _ffprobe_bin


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
    global _ffmpeg_ok_cache
    if _ffmpeg_ok_cache is not None:
        return _ffmpeg_ok_cache
    _ffmpeg_ok_cache = bool(ffmpeg_bin() and ffprobe_bin())
    return _ffmpeg_ok_cache


def probe(path: Path) -> tuple[float, int]:
    probe_bin = ffprobe_bin()
    if not probe_bin:
        raise FFmpegError("ffprobe가 없습니다. start.bat을 다시 실행하세요.")
    with _ascii_input(path) as inn:
        r = _run(
            [
                probe_bin,
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
    ff = ffmpeg_bin()
    if not ff:
        raise FFmpegError("FFmpeg가 없습니다. start.bat을 다시 실행하세요.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ascii_pair(src, "out.flac") as (inn, out, _td):
        common = [ff, "-y", "-i", str(inn), "-vn", "-ar", "16000", "-ac", "1", "-c:a", "flac"]
        r = _run([*common, "-map", "0:a:0", str(out)])
        if r.returncode != 0 or not out.exists():
            out.unlink(missing_ok=True)
            r = _run([*common, str(out)])
        if r.returncode != 0 or not out.exists():
            raise FFmpegError(_human_ffmpeg(r.stderr) or "영상에서 오디오를 꺼내지 못했습니다")
        shutil.copy2(out, dest)


def cut_segment(src: Path, dest: Path, start: float, duration: float | None = None) -> None:
    ff = ffmpeg_bin()
    if not ff:
        raise FFmpegError("FFmpeg가 없습니다. start.bat을 다시 실행하세요.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _ascii_pair(src, "out.flac") as (inn, out, _td):
        args = [ff, "-y", "-ss", f"{start:.3f}", "-i", str(inn)]
        if duration is not None:
            args += ["-t", f"{duration:.3f}"]
        args += ["-c:a", "flac", "-ar", "16000", "-ac", "1", str(out)]
        r = _run(args)
        if r.returncode != 0 or not out.exists():
            raise FFmpegError(_human_ffmpeg(r.stderr) or "cut failed")
        shutil.copy2(out, dest)


def segment_by_time(src: Path, dest_dir: Path, target_sec: float) -> list[Path]:
    ff = ffmpeg_bin()
    if not ff:
        raise FFmpegError("FFmpeg가 없습니다. start.bat을 다시 실행하세요.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with _ascii_pair(src, "seg_%04d.flac") as (inn, pattern, td):
        r = _run(
            [
                ff,
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
                ff,
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
