from __future__ import annotations

import io
import re
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

from backend.services.audio_service import CREATE_NO_WINDOW, ffmpeg_bin, ffmpeg_ok

AUDIO_NAME = re.compile(r'"([^"]+)"\s*\(audio\)', re.I)
_SKIP_DEV = re.compile(r"stereo mix|what u hear|loopback|sound mapper|mapper", re.I)
_MIC_DEV = re.compile(r"mic|마이크|headset|헤드셋|array|배열", re.I)


class RecordError(Exception):
    pass


_lock = threading.Lock()
_mode: str | None = None
_stream: object | None = None
_chunks: list = []
_rate = 48000
_proc: subprocess.Popen[bytes] | None = None
_path: Path | None = None
_err_handle: object | None = None


def _decode_ff(raw: bytes) -> str:
    if not raw:
        return ""
    for enc in ("utf-8", "cp949", "mbcs", "cp1252"):
        try:
            text = raw.decode(enc)
            if "\ufffd" not in text:
                return text
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _dev_get(info: object, key: str, default=None):
    try:
        if isinstance(info, dict):
            return info.get(key, default)
        return info[key]  # type: ignore[index]
    except Exception:
        return getattr(info, key, default)


def _wav_bytes(samples, rate: int) -> bytes:
    import numpy as np

    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


def _close_ffmpeg() -> None:
    global _proc, _path, _err_handle
    proc, path, handle = _proc, _path, _err_handle
    _proc = None
    _path = None
    _err_handle = None
    if proc and proc.poll() is None:
        try:
            if proc.stdin:
                proc.stdin.write(b"q\n")
                proc.stdin.flush()
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    if handle is not None:
        try:
            handle.close()  # type: ignore[union-attr]
        except OSError:
            pass
    if path:
        path.unlink(missing_ok=True)
        path.with_suffix(".err").unlink(missing_ok=True)


def _close_portaudio() -> None:
    global _stream, _chunks
    stream = _stream
    _stream = None
    if stream is not None:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
    _chunks = []


def stop() -> bytes:
    global _mode
    with _lock:
        mode = _mode
        _mode = None
        chunks = list(_chunks)
        rate = _rate
        proc, path = _proc, _path
    if mode == "pa":
        _close_portaudio()
        if not chunks:
            raise RecordError("녹음 데이터가 비었습니다. 조금 더 말한 뒤 끝내세요.")
        import numpy as np

        data = _wav_bytes(np.concatenate(chunks, axis=0), rate)
        if len(data) < 256:
            raise RecordError("녹음 데이터가 비었습니다. 조금 더 말한 뒤 끝내세요.")
        return data
    if mode == "ffmpeg":
        data = b""
        if proc and proc.poll() is None:
            try:
                if proc.stdin:
                    proc.stdin.write(b"q\n")
                    proc.stdin.flush()
                    proc.stdin.close()
            except OSError:
                pass
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        if path and path.exists():
            data = path.read_bytes()
        _close_ffmpeg()
        if len(data) < 256:
            raise RecordError("녹음 데이터가 비었습니다. Discord를 종료한 뒤 다시 녹음하세요.")
        return data
    raise RecordError("진행 중인 녹음이 없습니다.")


def _try_portaudio_device(sd, index: int, info: object) -> bool:
    global _mode, _stream, _chunks, _rate
    channels = int(_dev_get(info, "max_input_channels") or 0)
    if channels < 1:
        return False
    rate = int(_dev_get(info, "default_samplerate") or 48000) or 48000
    got: list = []

    def callback(indata, frames, time_info, status, bucket=got):  # noqa: ARG001
        bucket.append(indata.copy())

    stream = None
    try:
        stream = sd.InputStream(
            device=index,
            samplerate=rate,
            channels=min(channels, 2),
            dtype="float32",
            latency="high",
            callback=callback,
        )
        stream.start()
        time.sleep(0.2)
        if stream.active and got:
            with _lock:
                _stream = stream
                _chunks = got
                _rate = rate
                _mode = "pa"
            return True
    except Exception:
        pass
    if stream is not None:
        try:
            stream.abort()
            stream.close()
        except Exception:
            pass
    return False


def _start_portaudio() -> bool:
    try:
        import sounddevice as sd
    except Exception:
        return False
    try:
        devices = sd.query_devices()
    except Exception:
        return False

    default_idx: int | None = None
    try:
        d = sd.default.device
        if isinstance(d, (list, tuple)):
            if d[0] is not None and int(d[0]) >= 0:
                default_idx = int(d[0])
        elif d is not None and int(d) >= 0:
            default_idx = int(d)
    except Exception:
        default_idx = None

    scored: list[tuple[int, int]] = []
    for index, info in enumerate(devices):
        channels = int(_dev_get(info, "max_input_channels") or 0)
        if channels < 1:
            continue
        name = str(_dev_get(info, "name") or "")
        score = 0
        if default_idx is not None and index == default_idx:
            score += 50
        if _MIC_DEV.search(name):
            score += 10
        if _SKIP_DEV.search(name):
            score -= 30
        scored.append((score, index))
    scored.sort(reverse=True)

    for _, index in scored[:6]:
        try:
            info = devices[index]
        except Exception:
            continue
        if _try_portaudio_device(sd, index, info):
            return True
    return False


def _wait_ffmpeg_file(proc: subprocess.Popen[bytes], dest: Path, handle, timeout: float) -> bool:
    global _mode, _proc, _path, _err_handle
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        if dest.exists() and dest.stat().st_size >= 1024:
            with _lock:
                _proc = proc
                _path = dest
                _err_handle = handle
                _mode = "ffmpeg"
            return True
        time.sleep(0.12)
    return False


def _kill_proc(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass


def _start_ffmpeg_backend(ffmpeg: str, extra_in: list[str]) -> bool:
    dest = Path(tempfile.gettempdir()) / f"nasnote-rec-{uuid.uuid4().hex}.wav"
    err_file = dest.with_suffix(".err")
    handle = err_file.open("wb")
    proc = subprocess.Popen(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            *extra_in,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=handle,
        creationflags=CREATE_NO_WINDOW,
    )
    if _wait_ffmpeg_file(proc, dest, handle, 2.2):
        return True
    _kill_proc(proc)
    handle.close()
    dest.unlink(missing_ok=True)
    err_file.unlink(missing_ok=True)
    return False


def _prefer_names(names: list[str]) -> list[str]:
    mics = [n for n in names if _MIC_DEV.search(n) and not _SKIP_DEV.search(n)]
    other = [n for n in names if n not in mics and not _SKIP_DEV.search(n)]
    skip = [n for n in names if _SKIP_DEV.search(n)]
    return mics + other + skip


def _start_ffmpeg_dshow(ffmpeg: str) -> bool:
    listed = subprocess.run(
        [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )
    text = _decode_ff(listed.stderr or b"") + "\n" + _decode_ff(listed.stdout or b"")
    names = _prefer_names(AUDIO_NAME.findall(text))
    if not names:
        return False
    for name in names[:6]:
        if _start_ffmpeg_backend(ffmpeg, ["-f", "dshow", "-i", f"audio={name}"]):
            return True
    return False


def _start_ffmpeg_wasapi(ffmpeg: str) -> bool:
    return _start_ffmpeg_backend(ffmpeg, ["-f", "wasapi", "-i", "default"])


def _start_ffmpeg() -> bool:
    if not ffmpeg_ok():
        return False
    ffmpeg = ffmpeg_bin()
    if not ffmpeg:
        return False
    if _start_ffmpeg_dshow(ffmpeg):
        return True
    if _start_ffmpeg_wasapi(ffmpeg):
        return True
    return False


def start() -> None:
    with _lock:
        old = _mode
    if old:
        try:
            stop()
        except RecordError:
            _close_portaudio()
            _close_ffmpeg()
    if _start_portaudio():
        return
    if _start_ffmpeg():
        return
    raise RecordError(
        "마이크를 열지 못했습니다. Discord를 완전히 종료하고, Windows 설정 → 개인 정보 보호 및 보안 → 마이크에서 데스크톱 앱 허용을 켠 뒤 다시 누르세요."
    )
