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

import numpy as np
import sounddevice as sd

from backend.services.audio_service import CREATE_NO_WINDOW, ffmpeg_ok

AUDIO_NAME = re.compile(r'"([^"]+)" \(audio\)')


class RecordError(Exception):
    pass


_lock = threading.Lock()
_mode: str | None = None
_stream: sd.InputStream | None = None
_chunks: list[np.ndarray] = []
_rate = 48000
_proc: subprocess.Popen[bytes] | None = None
_path: Path | None = None
_err_handle: object | None = None


def _wav_bytes(samples: np.ndarray, rate: int) -> bytes:
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


def _start_portaudio() -> bool:
    global _mode, _stream, _chunks, _rate
    devices = sd.query_devices()
    for index, info in enumerate(devices):
        channels = int(info.get("max_input_channels") or 0)
        if channels < 1:
            continue
        rate = int(info.get("default_samplerate") or 48000) or 48000
        got: list[np.ndarray] = []

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
            time.sleep(0.45)
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


def _start_ffmpeg() -> bool:
    global _mode, _proc, _path, _err_handle
    if not ffmpeg_ok():
        return False
    listed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True,
        creationflags=CREATE_NO_WINDOW,
    )
    text = (listed.stderr or b"").decode("utf-8", errors="replace")
    names = AUDIO_NAME.findall(text)
    if not names:
        return False
    dest = Path(tempfile.gettempdir()) / f"nasnote-rec-{uuid.uuid4().hex}.wav"
    err_file = dest.with_suffix(".err")
    for name in names:
        handle = err_file.open("wb")
        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-f",
                "dshow",
                "-i",
                f"audio={name}",
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
        deadline = time.time() + 2.5
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if dest.exists() and dest.stat().st_size >= 1024:
                with _lock:
                    _proc = proc
                    _path = dest
                    _err_handle = handle
                    _mode = "ffmpeg"
                return True
            time.sleep(0.15)
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        handle.close()
        dest.unlink(missing_ok=True)
        err_file.unlink(missing_ok=True)
    return False


def start() -> None:
    with _lock:
        if _mode:
            old = _mode
        else:
            old = None
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
