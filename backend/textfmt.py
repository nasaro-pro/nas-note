from __future__ import annotations

import json
import re


def unescape_text(text: str | None) -> str:
    cur = "" if text is None else str(text)
    for _ in range(4):
        nxt = cur.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")
        if nxt == cur:
            break
        cur = nxt
    return cur.replace('\\"', '"')


def _split_lines(text: str) -> list[str]:
    out: list[str] = []
    for line in re.split(r"\n+", unescape_text(text)):
        item = re.sub(r"^[-•*]\s+", "", line.strip())
        item = re.sub(r"^\d+[.)]\s+", "", item).strip()
        if item and item != "없음":
            out.append(item)
    return out


def as_str_list(raw: object) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", "replace")
    if isinstance(raw, str):
        text = raw.strip()
        if not text or text == "없음":
            return []
        try:
            raw = json.loads(text)
        except Exception:
            return _split_lines(text)
    if isinstance(raw, list):
        items: list[str] = []
        for value in raw:
            piece = unescape_text(str(value)).strip()
            if not piece or piece == "없음":
                continue
            if "\n" in piece:
                items.extend(_split_lines(piece))
            else:
                items.append(piece)
        return items
    text = unescape_text(str(raw)).strip()
    return [text] if text and text != "없음" else []
