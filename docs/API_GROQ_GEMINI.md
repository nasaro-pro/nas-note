# Groq Whisper + Gemini 연결

브라우저에서 두 API를 직접 치지 않는다. 백엔드만.

- STT: `backend/services/stt_service.py` — **Groq** (`GROQ_API_KEY`)
- 분석: `backend/services/gemini_service.py` — Gemini Pro (`GEMINI_API_KEY`)

xAI / Grok / `XAI_API_KEY` 는 쓰지 않는다.

---

## 1. Groq Speech-to-Text (Whisper)

문서: https://console.groq.com/docs/speech-to-text  
키: https://console.groq.com/keys

```
POST https://api.groq.com/openai/v1/audio/transcriptions
Authorization: Bearer $GROQ_API_KEY
```

패키지 `groq`. 공식 예시는 turbo지만 **우리는 `whisper-large-v3`** (정확도). 2~3회 사용.

| 필드 | 값 |
|---|---|
| file | 24MB 이하 청크 (flac/mp3/m4a/mp4/wav) |
| model | `whisper-large-v3` |
| language | `ko` |
| response_format | `verbose_json` |
| temperature | `0` |

화자 분리 파라미터 없음. `text`만 이어붙인다.

한도: 무료 직접 업로드 **25MB**. 그래서 분할 기준 24MB. 개발자 플랜은 100MB여도 24MB를 유지 (재시도 단위).

긴 파일은 Groq가 chunking을 공식 권장. 우리 파이프라인이 그것이다.

```python
from groq import Groq

def transcribe_chunk(path: Path) -> str:
    client = Groq(api_key=settings.groq_api_key)
    with path.open("rb") as f:
        out = client.audio.transcriptions.create(
            file=f,
            model=settings.groq_stt_model,
            language="ko",
            response_format="verbose_json",
            temperature=0,
        )
    return out.text
```

timeout 600s. 재시도 3회, 2/4/8s, 429/5xx.

조각 저장: `transcripts/part_XXXX.txt`.  
병합: `full_transcript.txt` = `"\n\n".join(parts 순서대로)`. 화면에 Part 헤더 없음.

---

## 2. Gemini 분석

모델 기본 `gemini-2.5-pro`. 패키지 `google-genai`.

6필드 JSON schema 강제. temperature 0.2.  
≤100,000자 1회, 초과 map-reduce.

키가 한쪽만 있을 때:

- Groq 없음 → 업로드 503
- Gemini만 없음 → 전사까지 한 뒤 분석 failed. 키 넣고 retry면 분석만

---

## 3. `.env`

```
GROQ_API_KEY=
GEMINI_API_KEY=
```

모델은 `.env.example`에 이미 `whisper-large-v3` / `gemini-2.5-pro`.
