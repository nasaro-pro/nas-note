# nas-note — 구현 확정 스펙 (파이프라인)

**개정:** 제품명 nas-note. STT는 **Groq Whisper** (`whisper-large-v3`). xAI Grok 아님. 현재 총정리는 **`SPEC.md`**. 이 파일의 Grok/XAI/녹음노트 서술은 SPEC이 이긴다.

화면은 `docs/SITE_DESIGN.md`, 필요물은 `docs/REQUIREMENTS.md`, API는 `docs/API_GROQ_GEMINI.md`, 일정은 `docs/DEV_PLAN.md`, 목업은 `design-preview/index.html`.

열린 항목은 모두 여기서 닫는다.

---

## 0. 한 줄 정의

```
업로드 → 24MB 분할 → 순차 Groq Whisper → 한 텍스트로 병합 → Gemini Pro 분석 → SQLite + 날짜 폴더 저장 → FTS5 검색
```

서버 인프라 없음. 클라우드 DB 없음. AI 채팅/벡터/RAG 없음.

---

## 1. 목적 · 원칙 · 비목표

### 목적

3~4시간 녹음을 올리고 자리를 비워도, 돌아오면 전체 텍스트와 요약/결정/TODO가 프로젝트로 남아 있어야 한다. 이후 프로젝트별·전체 텍스트 검색으로 다시 찾는다.

### 설계 원칙

| 원칙 | 의미 |
|---|---|
| 개인용, 로컬 우선 | 데이터는 `DATA_DIR` 아래 파일 + SQLite 한 개. 외부 DB/객체스토리지 금지 |
| 기능 최소화 | 검색은 FTS5만. 채팅/임베딩/RAG 금지 |
| 완전 자동 파이프라인 | 업로드 클릭 이후 사용자 확인 단계 없음 |
| 중단 복구 | Part 단위 idempotent. 서버 재시작 시 DB status만 보고 이어서 진행 |
| 단일 워커 | 한 번에 프로젝트 하나. 병렬 STT 금지 (순서 보장) |

### 명시적 비목표

- AI 채팅 인터페이스
- 벡터 DB / 임베딩 / RAG
- 실시간 스트리밍 STT (WebSocket STT 사용 안 함)
- 다중 사용자 / 계정 / 클라우드 동기화
- 화자별 타임라인 UI (diarize 결과는 텍스트에만 반영)
- Celery / Redis / Docker Compose 필수화

---

## 2. 구현 전에 닫은 결정 (3개 + 부수 결정)

원 설계의 “검토 필요” 3가지는 아래처럼 **고정**한다. Phase 4로 미루지 않는다.

### D1. STT 재시도 정책 — 고정

| 항목 | 값 |
|---|---|
| 총 시도 횟수 | **3회** (최초 1 + 재시도 2) |
| 간격 | exponential backoff **2s → 4s → 8s** (`2^attempt` 초, attempt=1,2,3) |
| 재시도 대상 | HTTP 429, 500, 502, 503, 504, timeout, 연결 오류 |
| 즉시 실패 | HTTP 400, 401, 403, 413, 파일 손상, FFmpeg 실패 |
| 청크 실패 시 | 해당 `CHUNKS.status = failed`, `PROJECTS.status = failed`, **나머지 청크는 건드리지 않음** |
| 사용자 알림 | 처리 화면 배너 + 프로젝트 목록 실패 뱃지. 메시지에 실패한 part 번호 |
| 재개 | `POST /projects/{id}/retry` → failed 청크만 다시 시도 (done은 건너뜀) |
| 재개 시 retry_count | 해당 청크 `retry_count`를 0으로 리셋 후 다시 3회 |

실패해도 이미 끝난 Part 텍스트는 디스크와 DB에 그대로 남긴다.

### D2. Gemini 분할 분석 — map-reduce 2단계 고정

```
전체 transcript
    ├─ 길이 ≤ 100,000자  →  단일 Gemini 호출 (최종 JSON 한 번에)
    └─ 길이 > 100,000자  →  MAP: 50,000자 단위 부분 요약
                              REDUCE: 부분 요약을 다시 Gemini에 넣어 최종 JSON
```

- MAP 조각은 원문을 concat하지 않는다. 각 조각은 “부분 요약 JSON”만 만든다.
- REDUCE만 사용자에게 보이는 6개 필드를 채운다.
- 조각 경계는 문단(`\n\n`) 우선, 없으면 문장(`.!?。？！`) 경계. 단어 중간 절단 금지.
- 조각 간 **500자 overlap** (앞 조각 꼬리를 다음 조각 머리에 붙임). MAP 프롬프트에 “중복 구간이 있을 수 있음, 한 번만 반영”을 명시.

### D3. chunks 삭제 시점 — 고정

| 시점 | 동작 |
|---|---|
| STT 진행 중 | `chunks/` 유지 (재시도에 필요) |
| `PROJECTS.status = done` 직후 | **`chunks/` 디렉터리 전체 삭제** |
| 원본 `original/` | **유지** (재STT 시 다시 분할) |
| `transcripts/` · `full_transcript.txt` · `analysis.json` | **유지** |
| Phase 4 | 프로젝트 삭제 시 폴더 전체 삭제. “원본만 삭제” 버튼은 Phase 4 |

분석이 끝나기 전에 실패하면 chunks는 남긴다. 재개가 가능해야 하기 때문이다.

### 부수 결정 (원안에 열려 있던 것)

| 항목 | 고정값 | 이유 |
|---|---|---|
| 분할 경계 overlap | **MVP에서 없음** (문장 중간 절단 허용) | Part 10개 안팎, 손실 미미. 품질 문제 생기면 무음 분할을 후속 |
| 백그라운드 | 프로세스 내 **단일 asyncio 워커 루프** + DB 상태 + 프론트 **2초 폴링** | Celery/RQ 과함 |
| FastAPI BackgroundTasks | 사용하지 않음. 앱 시작 시 worker task를 `asyncio.create_task`로 고정 실행 | BackgroundTasks는 요청 수명에 묶임 |
| STT 병렬 | **금지**. chunk_index 오름차순 1개씩 | 순서·레이트 리밋 |
| 분할 기준 24MB | Groq 무료 직접 업로드 25MB. 1MB 여유 |
| 마지막 조각 | `24MB < last < 48MB`이면 **이등분** | 원안 그대로 |
| STT 언어 | `language=ko`, `format=true` | 한국어 회의가 주 사용 |
| 화자 분리 | `diarize=true`. 텍스트에 `화자 N:` 프리픽스로 저장 | 분석 품질. 별도 UI는 안 만듦 |
| Gemini 모델 | `GEMINI_MODEL` env, 기본 `gemini-2.5-flash` | 변경 가능하게 |
| 청크 파일명 | `part_0001.mp3` 4자리 zero-pad | 정렬 꼬임 방지 |
| 프로젝트 폴더명 | `{id:04d}_{YYYY-MM-DD}_{slug}` | id가 앞에 있어 충돌 없음 |

---

## 3. 기술 스택

| 영역 | 기술 | 비고 |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite | 라우터: React Router |
| Backend | Python 3.12 + FastAPI + Uvicorn | |
| 음성 | FFmpeg / ffprobe | PATH에 설치되어 있어야 함. 시작 시 존재 검사 |
| STT | Groq Whisper `whisper-large-v3` | `POST .../openai/v1/audio/transcriptions`, 25MB 한도 |
| 분석 | Gemini `gemini-2.5-pro` JSON schema | |
| DB | SQLite + FTS5, WAL | `aiosqlite` 또는 FastAPI sync + thread |
| HTTP 클라이언트 | `httpx` | timeout 명시 |
| 프론트 통신 | Vite proxy `/api` → `localhost:8000` | |

### 환경 변수

```
GROQ_API_KEY=          # 필수. Groq Whisper
GEMINI_API_KEY=        # 필수. 분석
GROQ_STT_MODEL=whisper-large-v3
GEMINI_MODEL=gemini-2.5-pro
DATA_DIR=./data
HOST=127.0.0.1
PORT=8000
```

키는 `.env`에만 둔다. 프론트에 노출 금지. 레포에 `.env` 커밋 금지.

---

## 4. 전체 파이프라인 (상태 머신)

### 4.1 PROJECTS.status

```
pending
  → splitting
  → transcribing
  → analyzing
  → done
       ↘ failed   (splitting / transcribing / analyzing 어느 단계에서든)
```

`failed`에서 `POST /projects/{id}/retry` → 실패 단계로 되돌린 뒤 워커가 재소비.

| 실패 단계 | retry 시 복귀 status | 동작 |
|---|---|---|
| splitting 중 실패 | `pending` | 분할부터 다시. 기존 chunks 폴더 지우고 재분할 |
| transcribing 중 실패 | `transcribing` | `CHUNKS.status=done`은 skip. failed/pending만 처리 |
| analyzing 중 실패 | `analyzing` | STT는 이미 끝났으므로 Gemini만 다시 |

### 4.2 CHUNKS.status

```
pending → processing → done
                   ↘ failed
```

`processing`인 채로 프로세스가 죽으면, 워커 재시작 시 그 청크를 `pending`으로 되돌린다 (부분 기록된 txt가 있으면 삭제 후 재STT).

### 4.3 단계별 동작

```
[업로드]
  파일을 original/ 에 저장
  PROJECTS row insert, status=pending
  워커 큐에 project_id put

[splitting]
  ffprobe로 duration, size
  24MB 이하면 part_0001로 복사(또는 동일 포맷 유지)
  초과면 시간 추정 분할 → 용량 재검사 → 필요 시 재분할
  마지막 조각 24~48MB면 이등분
  assert 모든 조각 ≤ 24MB
  CHUNKS rows insert (pending)
  status=transcribing

[transcribing]
  chunk_index 오름차순
  done → skip
  processing → STT → transcripts/part_XXXX.txt + TRANSCRIPTS row
  FTS insert
  전부 done이면 full_transcript.txt 병합, status=analyzing

[analyzing]
  길이 검사 → 단일 또는 map-reduce
  analysis.json + summary.txt 저장
  ANALYSES row + FTS
  chunks/ 삭제
  status=done

[어느 단계든 예외]
  로깅, status=failed, error_message 기록
```

---

## 5. 음성 분할 (splitter_service)

### 상수

```python
MAX_CHUNK_BYTES = 24 * 1024 * 1024  # 25,165,824
SAFETY_RATIO = 0.92                 # bitrate 추정 오차 여유
```

Grok STT 실제 한도는 500MB다. 그래도 **24MB를 지킨다**. 이유: Part 단위 재시도, 진행률 UI, 한 번의 timeout으로 3시간을 잃지 않기 위함.

### 알고리즘

```
def split_audio(src):
    size = filesize(src)
    duration = ffprobe_duration(src)   # 초, float

    if size <= MAX_CHUNK_BYTES:
        return [copy(src, "part_0001" + ext)]

    bytes_per_sec = size / duration
    target_sec = (MAX_CHUNK_BYTES / bytes_per_sec) * SAFETY_RATIO

    raw_chunks = ffmpeg_segment_by_time(src, target_sec)
    # ffmpeg: -f segment -segment_time {target_sec} -reset_timestamps 1
    # 1차: -c copy (빠름). 실패하거나 조각이 한도를 넘으면 해당 조각만 re-encode

    out = []
    for c in raw_chunks:
        out.extend(ensure_under_limit(c))

    last = out[-1]
    if MAX_CHUNK_BYTES < filesize(last) < 2 * MAX_CHUNK_BYTES:
        out[-1:] = split_in_half(last)

    assert all(filesize(c) <= MAX_CHUNK_BYTES for c in out)
    return rename_sequential(out)  # part_0001, part_0002, ...
```

`ensure_under_limit`:

1. size ≤ 24MB → 그대로
2. `-c copy` 조각이 넘치면 해당 조각만 **모노 64kbps AAC/MP3로 re-encode** 후 다시 시간 분할
3. 그래도 넘치면 `target_sec`를 절반으로 줄여 재귀. 깊이 상한 8. 넘으면 splitting 실패

`split_in_half`: ffprobe duration의 50% 지점에서 `-ss` / `-t`로 두 조각.

### FFmpeg 의존

앱 시작 시 `ffmpeg -version`, `ffprobe -version` 실패하면 `/health`가 degraded를 반환하고 업로드는 422.

지원 확장자: `.mp3 .wav .m4a .mp4 .aac .flac .ogg .opus .mkv` (원안 4종 + FFmpeg가 받는 추가. 업로드 UI는 원안 4종을 기본으로 열고, 나머지는 accept에 포함해도 됨).

MVP 업로드 accept: `audio/mpeg, audio/wav, audio/mp4, audio/x-m4a, video/mp4`.

### 경계 문제

MVP는 overlap/무음 감지 없음. 후속(Phase 5 이후, 비목표)에서 silence detect를 넣을 자리만 주석으로 남긴다.

---

## 6. Grok STT (stt_service)

### 엔드포인트

```
POST https://api.x.ai/v1/stt
Authorization: Bearer $XAI_API_KEY
Content-Type: multipart/form-data
```

필드 순서: 옵션 먼저, **`file`은 마지막**.

| 필드 | 값 |
|---|---|
| language | `ko` |
| format | `true` |
| diarize | `true` |
| filler_words | `false` |
| file | 청크 바이너리 |

timeout: connect 30s, read **600s** (긴 청크 대비).

### 응답 처리

`result["text"]`를 기본으로 쓴다. `diarize=true`이면 `words[].speaker`로 화자가 바뀌는 지점마다 줄바꿈 + `화자 {n}: ` 프리픽스를 붙여 저장한다. words가 없거나 speaker가 없으면 원문 `text`만 저장.

저장 위치:

- 파일: `transcripts/part_0001.txt`
- DB: `TRANSCRIPTS.content`
- FTS: `TRANSCRIPTS_FTS`

### 재시도 의사코드

```
async def transcribe_chunk(chunk):
    for attempt in (1, 2, 3):
        try:
            mark processing
            text = await grok_stt(chunk.path)
            save text
            mark done, retry_count 유지
            return
        except NonRetryable as e:
            mark failed, project failed, raise
        except Retryable as e:
            chunk.retry_count = attempt
            if attempt == 3:
                mark failed, project failed, raise
            await sleep(2 ** attempt)  # 2, 4, 8
```

워커는 프로젝트 하나 안에서 청크를 순차로 돌린다. 한 청크가 최종 실패하면 **그 프로젝트는 즉시 중단**. 다음 청크를 시작하지 않는다. 이미 done인 앞 청크는 보존.

---

## 7. 텍스트 병합 (transcript_service)

```
full = "\n\n".join(
    read(f"transcripts/part_{i:04d}.txt")
    for i in sorted(done_chunk_indexes)
)
write("full_transcript.txt", full)
```

Part 구분 헤더는 **사용자용 full_transcript에는 넣지 않는다**. (원안: 사용자에게 Part 구분 없이 표시)

디버깅용으로 `analysis.json` 옆이 아니라 transcripts 폴더에 part 파일을 남긴다.

병합은 모든 청크가 `done`일 때만 수행. 재개 후 마지막 청크가 끝나면 다시 병합(덮어쓰기).

---

## 8. Gemini 분석 (gemini_service)

### 출력 스키마 (사용자에게 보이는 6필드)

```json
{
  "overall_summary": "",
  "key_points": [],
  "detailed_summary": "",
  "decisions": [],
  "todos": [],
  "important": []
}
```

| 필드 | 화면 라벨 | 타입 |
|---|---|---|
| overall_summary | 전체 요약 | string, 8~15문장 목표 |
| key_points | 핵심 내용 | string[] 주제 목록 |
| detailed_summary | 상세 요약 | string, 흐름 순서 |
| decisions | 결정 사항 | string[] 확정된 것만. 없으면 빈 배열 |
| todos | 할 일 | string[] 가능하면 담당/기한 포함. 없으면 빈 배열 |
| important | 중요 내용 | string[] 중요 발언/수치/약속 |

DB 컬럼 `key_points`, `decisions`, `todos`는 JSON 배열을 TEXT로 저장. `important`는 원 스키마에 없었으므로 **ANALYSES.important TEXT** 컬럼을 추가한다. `detailed_summary`는 원안 유지.

### 프롬프트 규칙

- 시스템: “너는 한국어 회의록 분석기다. 추측하지 마라. transcript에 없는 사실을 만들지 마라. 결정/할 일이 없으면 빈 배열.”
- 응답은 JSON schema strict.
- 입력에 프로젝트 title을 힌트로 넣는다.

### MAP 프롬프트

부분 구간만 요약. 같은 6필드지만 “이 구간에 한정”. 결정/TODO는 이 구간에서 관찰된 것만.

### REDUCE 프롬프트

부분 JSON 배열을 입력으로 받아 중복 제거, 시간 흐름 정렬, 최종 6필드 생성. 원문 transcript는 REDUCE에 넣지 않는다 (토큰 절약). 부분 요약이 빈약하면 overall_summary에 “일부 구간 요약이 짧음” 같은 메타 문구는 넣지 말고 있는 정보만 통합.

### 실패

Gemini 재시도는 STT와 **동일 정책** (3회, 2/4/8s, 429/5xx). Non-retryable이면 analyzing 실패. 부분 MAP 중 하나가 실패하면 전체 analyzing 실패 (중간 MAP 결과는 `work/map_*.json`에 남겨 재개 시 성공분은 skip).

MAP 중간 산출물 경로: `projects/.../work/map_01.json`. `done` 시 `work/`도 삭제.

---

## 9. 로컬 저장 레이아웃

```
DATA_DIR/
├── app.db
└── projects/
    └── 0007_2026-09-01_회의/
        ├── original/
        │   └── meeting.mp3
        ├── chunks/                 # done 이후 삭제
        │   ├── part_0001.mp3
        │   └── ...
        ├── transcripts/
        │   ├── part_0001.txt
        │   └── ...
        ├── work/                   # analyzing 중만. done 이후 삭제
        │   └── map_01.json
        ├── full_transcript.txt
        ├── summary.txt             # overall_summary 평문
        ├── analysis.json           # 6필드 JSON
        └── project.json            # id, title, status, 경로 메타
```

`project.json`은 DB의 미러. DB가 소스 오브 트루스. 파일은 사람이 폴더만 열어봐도 결과를 볼 수 있게 하는 용도.

디스크 대략: 3~4시간 MP3 200MB면 처리 중 원본+청크 ≈ 400MB. 완료 후 청크 삭제 → 원본 200MB + 텍스트 수 MB.

---

## 10. DB 스키마

SQLite, `PRAGMA journal_mode=WAL;`, `foreign_keys=ON`.

```sql
CREATE TABLE projects (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  title             TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  rel_dir           TEXT NOT NULL,          -- projects/0007_2026-09-01_...
  duration          REAL,                   -- 초
  file_size         INTEGER,
  status            TEXT NOT NULL,          -- pending/splitting/transcribing/analyzing/done/failed
  error_message     TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE chunks (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,             -- 1-based
  filename    TEXT NOT NULL,
  file_size   INTEGER,
  status      TEXT NOT NULL,                -- pending/processing/done/failed
  retry_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  UNIQUE(project_id, chunk_index)
);

CREATE TABLE transcripts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content     TEXT NOT NULL,
  UNIQUE(project_id, chunk_index)
);

CREATE TABLE analyses (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id       INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  overall_summary  TEXT,
  key_points       TEXT,                    -- JSON array
  detailed_summary TEXT,
  decisions        TEXT,                    -- JSON array
  todos            TEXT,                    -- JSON array
  important        TEXT                     -- JSON array
);

CREATE VIRTUAL TABLE transcripts_fts USING fts5(
  content,
  project_id UNINDEXED,
  content='transcripts',
  content_rowid='id'
);

CREATE VIRTUAL TABLE analyses_fts USING fts5(
  overall_summary,
  key_points,
  detailed_summary,
  decisions,
  todos,
  important,
  project_id UNINDEXED,
  content='analyses',
  content_rowid='id'
);
```

FTS 동기화는 `transcripts`/`analyses` INSERT/UPDATE/DELETE 트리거로 맞춘다. 검색 토큰라이저는 `unicode61` (한글 부분일치에 한계가 있음). MVP는 FTS5 기본 + `LIKE` 폴백을 검색 서비스에 둔다.

- 사용자 쿼리를 FTS5 MATCH로 시도
- 한글 2글자 이상이고 히트가 0이면 `content LIKE '%'||q||'%'` 폴백 (프로젝트 규모가 작아서 허용)

인덱스:

```sql
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_chunks_project ON chunks(project_id, chunk_index);
```

---

## 11. 워커 (processing_worker)

앱 수명과 같은 **단일 코루틴**.

```
queue: asyncio.Queue[project_id]

startup:
  processing 상태 청크 → pending 롤백
  status IN (pending, splitting, transcribing, analyzing) 인 프로젝트를 created_at 순으로 queue put
  asyncio.create_task(worker_loop())

worker_loop:
  while True:
    project_id = await queue.get()
    try:
      await process_project(project_id)
    except Exception:
      log, mark failed
    finally:
      queue.task_done()

업로드/재개 핸들러:
  queue.put_nowait(project_id)
```

동시에 돌아가는 프로젝트는 1개. 큐에 쌓인 나머지는 목록에서 `대기 중`으로 표시 (`pending`).

진행률 계산 (폴링 응답):

```
if splitting: percent = 5
if transcribing:
  percent = 5 + 80 * (done_chunks / total_chunks)
if analyzing: percent = 90
if done: percent = 100
if failed: percent = 한 값 유지, status=failed
```

ETA는 넣지 않는다 (STT 시간이 파일마다 다름).

---

## 12. HTTP API

베이스: `/api`. 프론트는 Vite proxy.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | `{status, ffmpeg, db}` |
| POST | `/projects` | multipart `file` + optional `title` |
| GET | `/projects` | 목록. `?q=` 없이 최신순 |
| GET | `/projects/{id}` | 상세 + chunks + analysis (있으면) |
| GET | `/projects/{id}/status` | 폴링용 경량 상태 |
| GET | `/projects/{id}/transcript` | `full_transcript` 텍스트 |
| POST | `/projects/{id}/retry` | failed만 재개 |
| DELETE | `/projects/{id}` | Phase 4. MVP에서도 구현(폴더+row 삭제). 목록 관리에 필요 |
| GET | `/search?q=` | FTS. 프로젝트 title/transcript/analysis 히트 |

### POST /projects

- 파일 없으면 400
- 확장자 미지원 400
- 저장 후 201 `{id, status: "pending"}`
- 즉시 큐에 넣고 반환 (처리 완료를 기다리지 않음)

### GET /projects/{id}/status

```json
{
  "id": 7,
  "status": "transcribing",
  "percent": 42,
  "error_message": null,
  "chunks": [
    {"chunk_index": 1, "status": "done", "file_size": 23000000},
    {"chunk_index": 2, "status": "processing"},
    {"chunk_index": 3, "status": "pending"}
  ]
}
```

### GET /search?q=

```json
{
  "query": "배포 일정",
  "results": [
    {
      "project_id": 7,
      "title": "회의",
      "status": "done",
      "snippet": "...배포 일정은 금요일...",
      "source": "transcript"
    }
  ]
}
```

`source`: `transcript` | `analysis` | `title`

---

## 13. 화면 구조

라우트:

| 경로 | 화면 |
|---|---|
| `/` | 홈: 새 분석, 검색창, 프로젝트 목록 |
| `/upload` | 파일 선택 + 제목 입력 + 시작 |
| `/projects/:id` | 처리 중이면 진행 화면, done이면 결과 화면. failed면 재개 버튼 |
| `/search?q=` | 검색 결과 (홈 검색과 동일 컴포넌트여도 됨) |

### 홈

- 상단: 앱 이름, `[새 분석]`, 검색 input
- 목록: title, 날짜, duration, status 뱃지, 파일 크기
- 클릭 → 프로젝트 상세

### 업로드

- drag-and-drop + 파일 버튼
- title 기본값 = 파일명 stem
- 제출 중 버튼 비활성
- 성공 시 `/projects/:id`로 이동

### 처리 화면

- 프로젝트 title
- 전체 percent 바
- Part 리스트: `Part 03/11` + 대기/처리중/완료/실패
- 2초마다 `/status` 폴링. `done`/`failed`면 폴링 중지
- failed: error_message + `[이어서 재시도]`

### 결과 화면

탭 2개:

1. **전체 텍스트** — `full_transcript.txt` 스크롤. 복사 버튼
2. **AI 분석** — 6개 섹션을 위에서 아래로. 빈 배열은 “없음”

Phase 4에서 삭제 버튼.

상태 뱃지 색: pending 회색, 진행 파랑, done 초록, failed 빨강. (프론트 CSS)

---

## 14. 백엔드 디렉터리

```
backend/
├── main.py                 # FastAPI app, lifespan에서 db+worker
├── config.py               # env
├── api/
│   ├── health.py
│   ├── projects.py
│   ├── processing.py       # status, retry
│   └── search.py
├── services/
│   ├── audio_service.py
│   ├── splitter_service.py
│   ├── stt_service.py
│   ├── transcript_service.py
│   ├── gemini_service.py
│   └── search_service.py
├── workers/
│   └── processing_worker.py
├── database/
│   ├── db.py
│   └── models.py           # SQL / dataclass
└── storage/
    └── project_storage.py
```

프론트:

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api.ts
│   ├── types.ts
│   └── pages/
│       ├── HomePage.tsx
│       ├── UploadPage.tsx
│       └── ProjectPage.tsx
└── vite.config.ts          # proxy /api
```

루트:

```
/
├── DESIGN.md
├── README.md               # 실행 방법, FFmpeg 설치
├── .env.example
├── .gitignore
├── backend/
└── frontend/
```

---

## 15. 개발 순서 (구현 체크리스트)

Phase 1 안에 재시도·상태 스키마를 포함한다. Phase 4로 미루지 않는다.

### Phase 1 — 핵심 파이프라인

1. 레포 골격, `.env.example`, FFmpeg health check
2. SQLite 스키마 + WAL
3. `POST /projects` 업로드, `original/` 저장
4. splitter 24MB + 재검사 + 마지막 이등분 + part_0001 네이밍
5. 워커 루프 + 상태 머신
6. Grok STT 순차 + 3회 backoff + idempotent skip
7. part txt + full_transcript 병합
8. 프론트: 업로드 + 처리 화면 폴링

### Phase 2 — Gemini

1. JSON schema 호출
2. 100k 분기 + map-reduce + work/ 중간저장
3. analysis.json / summary.txt / ANALYSES
4. 결과 화면 2탭
5. done 시 chunks/ · work/ 삭제

### Phase 3 — 목록·검색

1. 홈 프로젝트 목록
2. 이전 결과 재조회
3. FTS5 + LIKE 폴백
4. 검색 결과 → 프로젝트 이동

### Phase 4 — 안정성 마무리

1. 프로젝트 삭제 (DB cascade + 폴더 rm)
2. 원본만 삭제 (optional)
3. 실패 배너/로그 파일 `DATA_DIR/logs/app.log`
4. 동시 업로드 여러 개 → 큐 대기 UI
5. `processing` 고아 청크 롤백 (이미 Phase 1 워커에 포함됐는지 확인)

---

## 16. 에러 · 로깅

| 상황 | HTTP/상태 | 사용자 메시지 |
|---|---|---|
| FFmpeg 없음 | 업로드 503 | FFmpeg가 설치되어 있지 않습니다 |
| API 키 없음 | 업로드 503 | XAI_API_KEY 또는 GEMINI_API_KEY가 없습니다 |
| 빈 파일 | 400 | 파일이 비어 있습니다 |
| STT 3회 실패 | project failed | Part 0004 전사에 실패했습니다. 이어서 재시도할 수 있습니다 |
| Gemini 실패 | project failed | 분석에 실패했습니다. 텍스트는 저장되어 있습니다. 재시도하면 분석만 다시 합니다 |
| 디스크 부족 | failed | 저장 공간이 부족합니다 |

로그: stderr + `DATA_DIR/logs/app.log`. 요청에 API 키를 찍지 않는다.

---

## 17. 설정 상수 모음 (`config.py`)

```python
MAX_CHUNK_BYTES = 24 * 1024 * 1024
SPLIT_SAFETY_RATIO = 0.92
STT_MAX_ATTEMPTS = 3
STT_BACKOFF_BASE = 2          # seconds, exponential
STT_READ_TIMEOUT = 600
GEMINI_MAP_THRESHOLD_CHARS = 100_000
GEMINI_MAP_CHUNK_CHARS = 50_000
GEMINI_MAP_OVERLAP_CHARS = 500
POLL_HINT_MS = 2000           # 프론트 폴링 간격 (문서용)
WORKER_ROLLBACK_PROCESSING = True
DELETE_CHUNKS_ON_DONE = True
DELETE_WORK_ON_DONE = True
KEEP_ORIGINAL_ON_DONE = True
STT_LANGUAGE = "ko"
STT_FORMAT = True
STT_DIARIZE = True
```

---

## 18. 구현 시 하지 말 것

- 청크 병렬 STT
- 업로드 요청이 STT가 끝날 때까지 블로킹
- Celery 도입
- 벡터 DB
- 결과 화면 채팅창
- chunks를 done 이후에도 기본 보관
- 25MB 초과 청크를 API로 보내기 (assert에서 막기)
- 프론트에서 API 키 사용

---

## 19. 수락 기준 (이 스펙으로 만들었다고 말할 수 있는 조건)

1. 24MB 이하 파일은 분할 없이 STT → 분석 → 저장까지 자동
2. 24MB 초과 파일은 모든 조각 ≤ 24MB, 이름은 `part_0001`부터
3. 처리 화면에서 Part별 상태가 2초 폴링으로 갱신
4. STT 중간 강제 종료 후 재시작해도 done Part는 다시 안 함
5. STT를 3번 실패시키면 프로젝트가 failed가 되고, retry 시 그 Part부터
6. 긴 텍스트는 map-reduce, 짧은 텍스트는 단일 호출. 결과는 6필드
7. done 후 `chunks/` 없음, `original/` 있음
8. 홈에서 키워드 검색이 transcript 또는 요약을 찾음
9. 채팅/RAG/벡터 코드가 코드베이스에 없음
