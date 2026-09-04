from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from backend.config import settings
from backend.storage import project_storage as store
from backend.textfmt import as_str_list, unescape_text

log = logging.getLogger("nas-note")
_resolved_model: str | None = None
_FALLBACK_MODELS = (
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3-pro-preview",
    "gemini-3-pro",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)

SYSTEM = (
    "너는 Groq Whisper 전사본으로 공부 내용을 정리하는 전문가다. "
    "음성 파일은 다시 듣지 마라. 아래 텍스트가 유일한 근거다. "
    "짧은 감상문이나 '이런 내용이다'로 끝내지 마라. 나중에 이 글만 보고 복습할 수 있게 적어라. "
    "원문에 없는 사실·배경지식·추측을 넣지 마라. 불확실하면 불확실하다고 밝혀라. "
    "말이 거의 없거나 음악·잡음이면 그 사실을 총정리에 적고 요약 정리는 짧게 둬라. "
    "원문이 한두 문장이면 출력도 짧게 끝내라. 분량을 채우려고 같은 말을 돌리지 마라. "
    "같은 단어·구절·문장을 두 번 이상 반복하지 마라. "
    "출력은 JSON 스키마만. 마크다운 울타리(```)를 넣지 마라. "
    "문자열 값에는 실제 줄바꿈을 넣어라. 백슬래시와 n 두 글자(\\n)를 넣지 마라.\n"
    "가독성:\n"
    "- 요약 정리는 ## 소제목으로 나누고, 소제목 앞뒤로 빈 줄을 넣어라.\n"
    "- 한 문단은 2~4문장. 문단 사이에 빈 줄을 넣어라. 한 덩어리로 붙이지 마라.\n"
    "- 배열 필드는 한 항목에 한 줄. 여러 항목을 한 문자열에 몰아넣지 마라.\n"
    "필드 역할:\n"
    "- overall_summary(총정리): 원문 길이에 맞게. 긴 강의면 6~12문장, 짧은 말이면 2~4문장. 문단을 나눠라.\n"
    "- extracted_info(정보 추가): 원문에 나온 이름, 날짜, 숫자, 장소, 고유명사, URL. "
    "'항목: 값' 한 줄. 뜻 설명은 넣지 마라. 없으면 빈 배열.\n"
    "- glossary(용어정리): 원문에 나온 전문용어, 약어, 개념. "
    "'용어: 원문에서 말한 뜻' 한 줄에 하나. 원문에 설명이 없으면 이름만. "
    "공부할 말이 있으면 비우지 마라. 여러 용어를 한 문자열에 몰아넣지 마라.\n"
    "- detailed_summary(요약 정리, 메인): 원문에 나온 설명을 빠짐없이 적되, "
    "원문이 짧으면 짧게 끝내라. 같은 문장을 늘려 쓰지 마라. "
    "긴 강의면 시간 순·주제 순으로 공부할 본문을 담아라. "
    "구간 노트면 그 구간만 채우고 앞뒤를 짐작하지 마라.\n"
    "- key_points(핵심 내용): 원문에 배울 점이 있으면 비우지 마라. "
    "정의, 원리, 비교, 강조점을 한 줄에 하나씩. 여러 문장을 한 문자열에 몰아넣지 마라.\n"
    "- decisions(결정 사항): 확정된 선택, 결론, 합의, 진행 방향. "
    "강의에서 결론을 냈으면 채워라. 없으면 빈 배열. '없음' 문자열을 넣지 마라.\n"
    "- todos: 숙제, 다음에 할 일, 따라 해 보라고 한 것.\n"
    "- important: 놓치면 안 되는 숫자, 기한, 이름, 예외, 강조점."
)


class AnalysisResult(BaseModel):
    overall_summary: str = ""
    extracted_info: list[str] = Field(default_factory=list)
    glossary: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    detailed_summary: str = ""
    decisions: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    important: list[str] = Field(default_factory=list)

    @field_validator("overall_summary", "detailed_summary", mode="before")
    @classmethod
    def _clean_text(cls, value: object) -> str:
        return unescape_text("" if value is None else str(value))

    @field_validator(
        "extracted_info",
        "glossary",
        "key_points",
        "decisions",
        "todos",
        "important",
        mode="before",
    )
    @classmethod
    def _clean_list(cls, value: object) -> list[str]:
        return as_str_list(value)


class MediaAnalysisResult(AnalysisResult):
    transcript: str = ""

    @field_validator("transcript", mode="before")
    @classmethod
    def _clean_transcript(cls, value: object) -> str:
        return unescape_text("" if value is None else str(value))


AUDIO_SYSTEM = (
    "너는 한국어 음성·영상 분석기다. 오디오를 직접 듣고 말한 내용을 받아 적은 뒤 "
    "그 내용만으로 정리하라. 들리지 않은 사실을 만들지 마라. "
    "말이 거의 없고 음악·효과음만 있으면 transcript에 확인된 가사나 짧은 멘트만 적고 "
    "분석은 실제로 들린 것만 채워라. 불확실하면 배열을 비워라. "
    "같은 구절을 반복하지 마라. 짧은 입력이면 짧게 끝내라. "
    "출력은 스키마를 지켜라. 마크다운 울타리를 넣지 마라. "
    "문자열에는 실제 줄바꿈을 넣고, 백슬래시와 n 두 글자(\\n)를 넣지 마라. "
    "핵심 내용, 결정 사항, 용어정리는 들린 내용이 있으면 배열로 채워라."
)

_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".webm": "video/webm",
    ".weba": "audio/webm",
}


class RetryableGeminiError(Exception):
    pass


class FatalGeminiError(Exception):
    pass


def _split_text(text: str) -> list[str]:
    limit = settings.gemini_map_chunk_chars
    overlap = settings.gemini_map_overlap_chars
    if len(text) <= settings.gemini_map_threshold_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + limit, n)
        if end < n:
            window = text[start:end]
            cut = window.rfind("\n\n")
            if cut < limit * 0.4:
                for sep in ("。", "！", "？", ".", "!", "?"):
                    pos = window.rfind(sep)
                    if pos > limit * 0.4:
                        cut = pos + 1
                        break
            if cut >= limit * 0.4:
                end = start + cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks or [text]


def _models_to_try() -> list[str]:
    ordered: list[str] = []
    for name in (_resolved_model, settings.gemini_model, *_FALLBACK_MODELS):
        text = (name or "").strip()
        if text and text not in ordered:
            ordered.append(text)
    return ordered


def _model_unavailable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(s in msg for s in ("404", "not_found", "not found", "no longer available"))


def _transient_gemini(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        s in msg
        for s in (
            "failed to fetch",
            "connect",
            "timeout",
            "timed out",
            "ssl",
            "proxy",
            "unavailable",
            "502",
            "503",
            "connection reset",
            "getaddrinfo",
            "temporarily",
            "network",
        )
    )


def _config_for(schema_cls: type, system: str, types: object, max_output_tokens: int = 24576):
    config_kwargs: dict = {
        "temperature": 0.2,
        "max_output_tokens": max_output_tokens,
        "response_mime_type": "application/json",
        "system_instruction": system,
    }
    try:
        config_kwargs["response_json_schema"] = schema_cls.model_json_schema()
        return types.GenerateContentConfig(**config_kwargs)
    except TypeError:
        config_kwargs.pop("response_json_schema", None)
        config_kwargs["response_schema"] = schema_cls
        return types.GenerateContentConfig(**config_kwargs)


def _config_plain(system: str, types: object, max_output_tokens: int = 24576):
    return types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json",
        system_instruction=system,
    )


def _token_budget(contents: object) -> int:
    if isinstance(contents, str):
        n = len(contents)
        if n < 200:
            return 2048
        if n < 800:
            return 4096
        if n < 4000:
            return 8192
        return 24576
    return 24576


def _cut_repeating_tail(text: str) -> tuple[str, bool]:
    n = len(text)
    if n < 40:
        return text, False
    window = text[-1200:] if n > 1200 else text
    max_unit = min(80, len(window) // 4)
    for size in range(max_unit, 3, -1):
        unit = window[-size:]
        if not unit.strip() or not re.search(r"[\w가-힣]", unit):
            continue
        reps = 1
        pos = len(window) - size
        while pos >= size and window[pos - size : pos] == unit:
            reps += 1
            pos -= size
        need = 4 if size >= 8 else 6
        if reps >= need:
            extra = size * (reps - 1)
            return text[: n - extra], True
    return text, False


def collapse_loops(text: str) -> tuple[str, bool]:
    if not text or len(text) < 32:
        return text, False
    looping = False
    cur = text
    nxt = re.sub(r"(?m)^(.+)$(?:\n\1){3,}", r"\1", cur)
    if nxt != cur:
        looping = True
        cur = nxt
    cur, tail_loop = _cut_repeating_tail(cur)
    if tail_loop:
        looping = True
    return cur, looping


def _extract_json_object(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _escape_newlines_in_strings(text: str) -> str:
    out: list[str] = []
    in_str = False
    escape = False
    for ch in text:
        if in_str:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                out.append(ch)
                in_str = False
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                continue
            elif ch == "\t":
                out.append("\\t")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_str = True
            out.append(ch)
    return "".join(out)


def _prepare_json(raw: str) -> str:
    text = _extract_json_object(raw)
    text = _escape_newlines_in_strings(text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _parse_json(raw: str, schema_cls: type):
    prepared = _prepare_json(raw)
    try:
        return schema_cls.model_validate_json(prepared)
    except Exception:
        data = json.loads(prepared)
        return schema_cls.model_validate(data)


def _wrap_sentences(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？])\s+", text) if p.strip()]
    if len(parts) < 4:
        return text
    paras: list[str] = []
    buf: list[str] = []
    size = 0
    for piece in parts:
        buf.append(piece)
        size += len(piece)
        if len(buf) >= 3 or size > 180:
            paras.append(" ".join(buf))
            buf = []
            size = 0
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras)


def polish_prose(text: str) -> str:
    cur = unescape_text(text).replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    cur = re.sub(r"[ \t]+\n", "\n", cur)
    cur = re.sub(r"\n[ \t]+", "\n", cur)
    cur = re.sub(r"[ \t]*#{1,3}[ \t]+", "\n\n## ", cur)
    cur = re.sub(r"\n##\s*\n", "\n\n", cur)
    cur = re.sub(r"\n{3,}", "\n\n", cur).strip()
    if cur.count("\n") < 3 and len(cur) > 360:
        cur = _wrap_sentences(cur)
    cur, _ = collapse_loops(cur)
    return cur.strip()


def polish_result(result: AnalysisResult) -> AnalysisResult:
    data = result.model_dump()
    data["overall_summary"] = polish_prose(data.get("overall_summary") or "")
    data["detailed_summary"] = polish_prose(data.get("detailed_summary") or "")
    if "transcript" in data:
        data["transcript"] = unescape_text(data.get("transcript") or "").strip()
    for key in ("extracted_info", "glossary", "key_points", "decisions", "todos", "important"):
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in data.get(key) or []:
            text, _ = collapse_loops(str(item))
            text = text.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        data[key] = cleaned
    return type(result).model_validate(data)


def _media_part(client: object, types: object, path: Path):
    mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
    data = path.read_bytes()
    inline_limit = 20 * 1024 * 1024
    if len(data) <= inline_limit:
        return types.Part.from_bytes(data=data, mime_type=mime)
    td = Path(tempfile.mkdtemp(prefix="nasnote_g_"))
    try:
        copy = td / f"media{path.suffix.lower() or '.bin'}"
        shutil.copy2(path, copy)
        return client.files.upload(file=str(copy))
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _client():
    from google import genai

    key = settings.gemini_api_key.strip()
    try:
        return genai.Client(api_key=key, http_options={"timeout": 300_000})
    except Exception:
        return genai.Client(api_key=key)


def _event_text(ev: object) -> str:
    bits: list[str] = []
    try:
        candidates = getattr(ev, "candidates", None) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                if getattr(part, "thought", False):
                    continue
                piece = getattr(part, "text", None)
                if piece:
                    bits.append(str(piece))
    except Exception:
        bits = []
    if bits:
        return "".join(bits)
    try:
        text = getattr(ev, "text", None)
        if text:
            return str(text)
    except Exception:
        pass
    return ""


def _accumulate_stream(acc: str, piece: str) -> str:
    if not piece:
        return acc
    if not acc or piece.startswith(acc):
        return piece
    if acc.startswith(piece) or acc.endswith(piece):
        return acc
    limit = min(len(acc), len(piece), 400)
    for n in range(limit, 0, -1):
        if acc[-n:] == piece[:n]:
            return acc + piece[n:]
    return acc + piece


def _write_draft(path: Path | None, text: str) -> None:
    if path is None or not str(text).strip():
        return
    store.write_text(path, text)


def _partial_json_string(raw: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"', raw)
    if not match:
        return ""
    i = match.end()
    out: list[str] = []
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(nxt, nxt))
            i += 2
            continue
        if ch == '"':
            break
        out.append(ch)
        i += 1
    return unescape_text("".join(out)).strip()


def _partial_json_list(raw: str, key: str) -> list[str]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[', raw)
    if not match:
        return []
    chunk = raw[match.end() :]
    end = chunk.find("]")
    body = chunk if end < 0 else chunk[:end]
    items: list[str] = []
    for piece in re.findall(r'"((?:[^"\\]|\\.)*)"', body):
        text = unescape_text(piece).strip()
        if text:
            items.append(text)
    return items


def _live_prose(text: str) -> str:
    cur = unescape_text(text).replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    cur = re.sub(r"[ \t]+\n", "\n", cur)
    cur = re.sub(r"[ \t]*#{1,3}[ \t]+", "\n\n## ", cur)
    cur = re.sub(r"\n##\s*\n", "\n\n", cur)
    cur = re.sub(r"\n{3,}", "\n\n", cur).strip()
    return cur


def live_analysis_text(raw: str) -> str:
    raw = (raw or "").strip()
    raw, _looping = collapse_loops(raw)
    if not raw:
        return "요약 정리를 작성하는 중입니다."
    try:
        parsed = _parse_json(raw, AnalysisResult)
        return format_analysis_text(polish_result(parsed), skip_empty=True)
    except Exception:
        pass
    overall = _live_prose(_partial_json_string(raw, "overall_summary"))
    detailed = _live_prose(_partial_json_string(raw, "detailed_summary"))
    result = AnalysisResult(
        overall_summary=overall,
        detailed_summary=detailed,
        extracted_info=_partial_json_list(raw, "extracted_info"),
        glossary=_partial_json_list(raw, "glossary"),
        key_points=_partial_json_list(raw, "key_points"),
        decisions=_partial_json_list(raw, "decisions"),
        todos=_partial_json_list(raw, "todos"),
        important=_partial_json_list(raw, "important"),
    )
    formatted = format_analysis_text(result, skip_empty=True)
    if formatted and formatted != "요약 정리를 작성하는 중입니다.":
        return formatted
    strings = [unescape_text(item).strip() for item in re.findall(r'"((?:[^"\\]|\\.){20,})"', raw)]
    skip = {
        "overall_summary",
        "detailed_summary",
        "extracted_info",
        "glossary",
        "key_points",
        "decisions",
        "todos",
        "important",
    }
    strings = [_live_prose(item) for item in strings if item and item not in skip]
    if strings:
        return max(strings, key=len)
    cleaned = unescape_text(raw).strip()
    if cleaned.startswith("{") or cleaned.startswith("```"):
        visible = re.sub(r"```(?:json)?", " ", cleaned)
        visible = re.sub(r'[{}\[\]"]+', " ", visible)
        visible = re.sub(
            r"\b(overall_summary|detailed_summary|extracted_info|glossary|key_points|decisions|todos|important)\b",
            " ",
            visible,
        )
        visible = re.sub(r"\s+", " ", visible).strip()
        return visible[:2000] if len(visible) > 24 else "요약 정리를 작성하는 중입니다."
    return _live_prose(cleaned) if cleaned else "요약 정리를 작성하는 중입니다."


def _generate_once(client: object, model: str, contents: object, config: object, draft_path: Path | None) -> str:
    acc = ""
    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        )
        for ev in stream:
            piece = _event_text(ev)
            if not piece:
                continue
            acc = _accumulate_stream(acc, piece)
            acc, looping = collapse_loops(acc)
            _write_draft(draft_path, live_analysis_text(acc))
            if looping:
                log.warning("gemini stream repeat stopped %s chars=%s", model, len(acc))
                break
        if acc.strip():
            acc, _ = collapse_loops(acc)
            return acc.strip()
    except Exception as exc:
        log.info("gemini stream fallback %s: %s", model, type(exc).__name__)
        if acc.strip():
            acc, _ = collapse_loops(acc)
            _write_draft(draft_path, live_analysis_text(acc))
            return acc.strip()
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    raw = (getattr(response, "text", None) or "").strip()
    if raw:
        raw, _ = collapse_loops(raw)
        _write_draft(draft_path, live_analysis_text(raw))
        return raw
    reason = ""
    try:
        reason = str(response.candidates[0].finish_reason)
    except Exception:
        pass
    if "SAFETY" in reason.upper():
        raise FatalGeminiError("모델이 이 내용을 분석하지 못했습니다.")
    return ""


def _generate_json(
    contents: object,
    schema_cls: type,
    system: str,
    draft_path: Path | None = None,
):
    from google.genai import types

    global _resolved_model
    client = _client()
    budget = _token_budget(contents)
    schema_config = _config_for(schema_cls, system, types, budget)
    plain_config = _config_plain(system, types, budget)
    last: Exception | None = None
    for model in _models_to_try():
        parsed = None
        for config in (plain_config, schema_config):
            try:
                raw = _generate_once(client, model, contents, config, draft_path)
            except FatalGeminiError:
                raise
            except Exception as exc:
                msg = str(exc).lower()
                if (
                    _model_unavailable(exc)
                    or _transient_gemini(exc)
                    or "not supported" in msg
                    or "inline" in msg
                    or "429" in msg
                    or "resource_exhausted" in msg
                    or "quota" in msg
                    or "ascii" in msg
                    or "invalid" in msg
                    or "schema" in msg
                ):
                    log.warning("gemini model skip %s: %s", model, type(exc).__name__)
                    last = exc
                    if _resolved_model == model:
                        _resolved_model = None
                    continue
                raise
            if not raw:
                last = RetryableGeminiError("빈 응답")
                continue
            try:
                parsed = polish_result(_parse_json(raw, schema_cls))
                break
            except Exception as exc:
                log.warning("gemini json parse fail %s: %s", model, type(exc).__name__)
                last = exc
                continue
        if parsed is None:
            continue
        _resolved_model = model
        log.info("gemini model in use: %s", model)
        if draft_path and isinstance(parsed, AnalysisResult):
            _write_draft(draft_path, format_analysis_text(parsed))
        return parsed
    if isinstance(last, RetryableGeminiError):
        raise last
    raise FatalGeminiError("사용 가능한 Gemini 모델이 없습니다.") from last


def _call_sync(prompt: str, draft_path: Path | None = None) -> AnalysisResult:
    return _generate_json(prompt, AnalysisResult, SYSTEM, draft_path)


def _analyze_media_sync(title: str, path: Path, draft_path: Path | None = None) -> MediaAnalysisResult:
    from google.genai import types

    client = _client()
    part = _media_part(client, types, path)
    prompt = (
        f"프로젝트 제목: {title}\n"
        "이 파일을 듣고 transcript와 분석 필드를 채워라."
    )
    return _generate_json([part, prompt], MediaAnalysisResult, AUDIO_SYSTEM, draft_path)


async def _call(prompt: str, draft_path: Path | None = None) -> AnalysisResult:
    last: Exception | None = None
    for attempt in (1, 2, 3):
        try:
            return await asyncio.to_thread(_call_sync, prompt, draft_path)
        except FatalGeminiError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if any(s in msg for s in ("400", "401", "403", "safety")):
                raise FatalGeminiError(str(exc)) from exc
            last = exc
            if attempt < 3:
                await asyncio.sleep(2**attempt)
    raise FatalGeminiError(str(last) if last else "분석 실패")


def _persist_analysis(rel_dir: str, result: AnalysisResult) -> None:
    result = polish_result(AnalysisResult.model_validate(result.model_dump()))
    root = store.project_root(rel_dir)
    body = format_analysis_text(result)
    store.write_json(root / "analysis.json", result.model_dump())
    store.write_text(root / "analysis.txt", body)
    store.write_text(root / "summary.txt", (result.detailed_summary or result.overall_summary or "").strip())
    draft = root / "analysis_draft.txt"
    if draft.exists():
        draft.unlink()


async def analyze(title: str, transcript: str, rel_dir: str) -> AnalysisResult:
    work = store.work_dir(rel_dir)
    work.mkdir(parents=True, exist_ok=True)
    root = store.project_root(rel_dir)
    draft = root / "analysis_draft.txt"
    store.write_text(draft, "요약 정리를 작성하는 중입니다.")
    pieces = _split_text(transcript)

    if len(pieces) == 1:
        short = len(pieces[0].strip()) < 120
        extra = (
            "원문이 매우 짧다. 총정리와 요약 정리를 짧게 끝내라. "
            "같은 구절을 반복하지 말고, 없는 내용을 늘리지 마라.\n\n"
            if short
            else "소제목(## 제목) 앞뒤로 빈 줄을 넣고, 문단도 빈 줄로 나눠라. "
            "원문에 있는 설명은 빼먹지 마라.\n\n"
        )
        prompt = (
            f"프로젝트 제목: {title}\n\n"
            "아래는 Groq Whisper 전사본이다. "
            f"{extra}"
            f"-----\n{pieces[0]}\n-----"
        )
        result = await _call(prompt, draft)
    else:
        partials: list[dict] = []
        for i, piece in enumerate(pieces, start=1):
            dest = work / f"map_{i:02d}.json"
            store.write_text(draft, f"요약 정리 {i}/{len(pieces)} 구간을 작성하는 중입니다.")
            if dest.exists():
                partials.append(json.loads(dest.read_text(encoding="utf-8")))
                continue
            prompt = (
                "이것은 Groq Whisper 전사본의 한 구간이다. 이 구간에만 있는 내용으로 "
                "공부 정리를 채워라. 요약 정리는 이 구간에서 나온 설명을 빼먹지 말고 "
                "길게 적어라. 앞뒤 구간을 추측하지 마라.\n"
                f"프로젝트 제목: {title}\n\n-----\n{piece}\n-----"
            )
            part = await _call(prompt, draft)
            store.write_json(dest, part.model_dump())
            partials.append(part.model_dump())
        reduce_prompt = (
            "아래는 시간 순 부분 정리 JSON 배열이다. 원문이 아닌 이 JSON만 근거로 삼아라. "
            "총정리는 전체를 관통하는 글로 다시 쓰고, 배열 필드는 중복만 빼서 합쳐라. "
            "요약 정리(detailed_summary)는 구간 내용을 이어서 쓰되 같은 문장을 반복하지 마라. "
            "각 구간의 요약 정리를 시간 순으로 이어서 하나의 긴 공부 정리로 만들고, "
            "소제목과 문단을 유지하라. 내용을 한 페이지로 줄이지 마라. "
            "핵심 내용·결정 사항·용어정리 배열은 비우지 말고 합쳐라. "
            "문자열에 \\n 두 글자를 넣지 말고 실제 줄바꿈을 넣어라.\n\n"
            + json.dumps(partials, ensure_ascii=False)
        )
        result = await _call(reduce_prompt, draft)

    _persist_analysis(rel_dir, result)
    return result


def format_analysis_text(result: AnalysisResult, *, skip_empty: bool = False) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items) if items else "없음"

    sections = [
        ("【총정리】", (result.overall_summary or "").strip()),
        ("【정보 추가】", bullets(result.extracted_info) if result.extracted_info else ""),
        ("【용어정리】", bullets(result.glossary) if result.glossary else ""),
        ("【요약 정리】", (result.detailed_summary or "").strip()),
        ("【핵심 내용】", bullets(result.key_points) if result.key_points else ""),
        ("【결정 사항】", bullets(result.decisions) if result.decisions else ""),
        ("【할 일】", bullets(result.todos) if result.todos else ""),
        ("【중요 내용】", bullets(result.important) if result.important else ""),
    ]
    blocks: list[str] = []
    for title, body in sections:
        text = body.strip()
        if skip_empty and not text:
            continue
        if not text:
            text = "없음"
        if blocks:
            blocks.append("")
        blocks.extend([title, text])
    return "\n".join(blocks).strip() or "요약 정리를 작성하는 중입니다."


async def analyze_media(title: str, path: Path, rel_dir: str) -> MediaAnalysisResult:
    last: Exception | None = None
    draft = store.project_root(rel_dir) / "analysis_draft.txt"
    store.write_text(draft, "요약 정리를 작성하는 중입니다.")
    for attempt in (1, 2, 3):
        try:
            result = await asyncio.to_thread(_analyze_media_sync, title, path, draft)
            break
        except FatalGeminiError:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if any(s in msg for s in ("401", "403", "safety")):
                raise FatalGeminiError(str(exc)) from exc
            last = exc
            if attempt < 3:
                await asyncio.sleep(2**attempt)
            else:
                raise FatalGeminiError(str(last) if last else "분석 실패") from last
    else:
        raise FatalGeminiError(str(last) if last else "분석 실패")

    root = store.project_root(rel_dir)
    _persist_analysis(rel_dir, result)
    if result.transcript.strip():
        store.write_text(root / "full_transcript.txt", result.transcript.strip())
    return result
