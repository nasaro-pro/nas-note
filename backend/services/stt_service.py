from __future__ import annotations

import asyncio
import re
from pathlib import Path

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq

from backend.config import settings


class RetryableSTTError(Exception):
    pass


class FatalSTTError(Exception):
    pass


def _seg_get(seg: object, key: str, default: object = None) -> object:
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def _collapse_repeats(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text) if p.strip()]
    if len(parts) >= 3 and len(set(parts)) <= 2:
        seen: list[str] = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return " ".join(seen)
    return text


def _text_from_result(out: object) -> str:
    segments = getattr(out, "segments", None) or []
    kept: list[str] = []
    for seg in segments:
        try:
            nsp = float(_seg_get(seg, "no_speech_prob", 0) or 0)
        except (TypeError, ValueError):
            nsp = 0.0
        try:
            alp = float(_seg_get(seg, "avg_logprob", 0) or 0)
        except (TypeError, ValueError):
            alp = 0.0
        piece = str(_seg_get(seg, "text", "") or "").strip()
        if not piece:
            continue
        if nsp > 0.6 or alp < -1.0:
            continue
        if kept and kept[-1] == piece:
            continue
        kept.append(piece)
    if kept:
        return _collapse_repeats(" ".join(kept))
    raw = str(getattr(out, "text", None) or "").strip()
    return _collapse_repeats(raw) if raw else ""


def _transcribe_sync(path: Path) -> str:
    client = Groq(api_key=settings.groq_api_key.strip(), timeout=600)
    ext = path.suffix.lower() or ".mp3"
    data = path.read_bytes()
    out = client.audio.transcriptions.create(
        file=(f"audio{ext}", data),
        model=settings.groq_stt_model,
        language="ko",
        response_format="verbose_json",
        temperature=0,
    )
    return _text_from_result(out)


async def transcribe_chunk(path: Path) -> str:
    last: Exception | None = None
    for attempt in (1, 2, 3):
        try:
            return await asyncio.to_thread(_transcribe_sync, path)
        except FatalSTTError:
            raise
        except APIStatusError as exc:
            code = getattr(exc, "status_code", None) or 0
            if code in (400, 401, 403, 413, 422):
                raise FatalSTTError(f"STT 거부 ({code})") from exc
            last = RetryableSTTError(str(exc))
        except (APITimeoutError, APIConnectionError, TimeoutError, OSError) as exc:
            last = RetryableSTTError(str(exc))
        except Exception as exc:
            msg = str(exc).lower()
            if "429" in msg or "timeout" in msg or "unavailable" in msg:
                last = RetryableSTTError(str(exc))
            else:
                raise FatalSTTError(str(exc)) from exc
        if attempt < settings.stt_max_attempts:
            await asyncio.sleep(2**attempt)
    raise FatalSTTError(str(last) if last else "STT 실패")
