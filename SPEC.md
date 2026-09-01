# nas-note — 설계·계획 총정리 (개정)

제품명 **nas-note**. 개인용 로컬 도구.

이전 초안의 “Grok Whisper / xAI”는 **잘못 짚은 것**이다. 사용자가 말한 건 **Groq**(https://console.groq.com)의 Whisper API다. 24MB 분할은 Groq 무료 한도 25MB와 맞는다.

이 문서가 현재 기준이다. 화면 픽셀은 `docs/SITE_DESIGN.md`, 목업은 `design-preview/index.html`.

---

## 0. 한 줄

```
긴 영상/음성 업로드
  → 날짜 폴더에 원본 저장
  → 24MB 이하 조각으로 분할 (Groq Whisper 한도)
  → 조각마다 순차 STT
  → 조각 텍스트를 하나의 full_transcript.txt 로 이어붙임
  → Gemini Pro로 정리·요약·결정·할 일
  → 사이트에서 바로 열람 + 전체 검색
```

2~3번 쓸 용도이므로 모델은 싼 쪽이 아니라 **윗단**을 기본값으로 둔다.

| 역할 | 제공자 | 기본 모델 | 키 |
|---|---|---|---|
| STT | Groq Whisper | `whisper-large-v3` (turbo 아님) | `GROQ_API_KEY` |
| 분석 | Gemini | `gemini-2.5-pro` (flash 아님) | `GEMINI_API_KEY` |

`.env`에 키 두 줄만 넣으면 된다. 모델명은 `.env.example`에 이미 박혀 있다.

---

## 1. 고친 점 (이전 초안 대비)

| 이전 | 지금 |
|---|---|
| 제품명 녹음노트 / Local Audio AI | **nas-note** |
| xAI Grok STT, `XAI_API_KEY` | **Groq** Whisper, `GROQ_API_KEY` |
| Grok 한도 500MB인데도 24MB | Groq **직접 업로드 25MB**(무료) / 100MB(유료). **24MB로 자른다** |
| `whisper` 화자 분리(diarize) | Groq Whisper는 diarize 없음. 연속 텍스트만 |
| Gemini `gemini-2.5-flash` | **`gemini-2.5-pro`** |
| 프로젝트 폴더가 날짜와 무관 | **날짜 폴더로 자동 정리**, 홈도 날짜 그룹 |
| 검색은 기능 목록 | 사이트에서 원문·요약 즉시 열람 + FTS5 검색이 핵심 UX |

---

## 2. Groq Whisper (조사 결과)

문서: https://console.groq.com/docs/speech-to-text  
키: https://console.groq.com/keys  
SDK: `pip install groq` → 환경변수 `GROQ_API_KEY`를 자동으로 읽음.

```
POST https://api.groq.com/openai/v1/audio/transcriptions
```

OpenAI Whisper와 같은 모양.

| 항목 | 값 |
|---|---|
| 모델 | `whisper-large-v3` — 다국어, WER 약 10.3%. turbo는 싸고 빠르지만 정확도가 떨어짐. 2~3회 용도면 **large-v3** |
| language | `ko` |
| response_format | `verbose_json` (세그먼트 타임스탬프, 디버깅용) |
| temperature | `0` |
| 직접 업로드 | 무료 **25MB**, 개발자 플랜 **100MB** |
| 포맷 | flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm |
| 권장 전처리 | 16kHz 모노 FLAC (`-ar 16000 -ac 1 -c:a flac`) |
| 긴 파일 | Groq가 공식으로 **chunking**을 권장. 우리가 하는 24MB 분할이 그 작업 |
| 화자 분리 | **없음**. 화자 N: 프리픽스를 STT에서 만들지 않음 |
| 가격 | large-v3 약 $0.111/시간. 3.5시간이면 약 $0.4 |

호출 스케치:

```python
from groq import Groq
client = Groq(api_key=settings.groq_api_key)

with open(chunk_path, "rb") as f:
    tr = client.audio.transcriptions.create(
        file=f,
        model="whisper-large-v3",
        language="ko",
        response_format="verbose_json",
        temperature=0,
    )
text = tr.text  # 이 조각의 전체 문자열
```

재시도: 3회, 2s/4s/8s, 429/5xx/timeout. 한 조각 실패 시 프로젝트 failed, 끝난 조각 텍스트는 남김.

순차만. 무료 플랜 RPM이 낮아서 병렬은 의미 없다.

---

## 3. 텍스트 변환 — “한 덩어리 → 조각 STT → 한 텍스트”

이게 제품의 본체다.

```
원본 1개 (3~4시간 mp4/m4a/mp3)
        │
        ├─ original/ 에 보관 (날짜 폴더 아래)
        │
        ▼
   16kHz 모노 FLAC로 맞춘 뒤
   24MB 이하 part_0001, part_0002, … 로 분할
        │
        ▼
   part_0001 → Groq → transcripts/part_0001.txt
   part_0002 → Groq → transcripts/part_0002.txt
   … 순서 고정, 끝난 조각은 다시 안 보냄
        │
        ▼
   full_transcript.txt  = part_0001 + "\n\n" + part_0002 + …
        │
        ▼
   사용자에게는 Part 구분 없이 이 한 파일만 보여 줌
```

- 조각 txt는 복구용으로 남긴다. 화면에는 안 나눈다.
- 사용자 결과 탭 이름은 **전체 텍스트**.
- 분할 전 원본이 영상(mp4)이어도 오디오 트랙만 떼서 분할한다 (Groq는 다중 트랙 중 첫 트랙만 씀).

---

## 4. Gemini 정리·요약

기본 모델 **`gemini-2.5-pro`**. Flash보다 비싸고 느리지만 회의 정리 품질이 목적이다. 2~3파일이면 충분. `.env`의 `GEMINI_MODEL`로 나중에 `gemini-3.1-pro-preview` 등으로 바꿀 수 있다.

JSON 스키마 6필드 (화면과 동일):

1. 전체 요약  
2. 핵심 내용  
3. 상세 요약  
4. 결정 사항  
5. 할 일  
6. 중요 내용  

10만 자 이하 1회 호출. 초과 시 부분 요약 → 최종 통합 (map-reduce). 추측 금지, 없으면 빈 배열.

사이트 **AI 분석** 탭에서 바로 본다.

---

## 5. 날짜별 자동 정리 (디스크 + 화면)

업로드 시각의 **로컬 달력 날짜**로 묶는다. 사용자가 날짜를 고르지 않는다.

### 디스크

```
data/
  nas-note.db
  projects/
    2026-09-01/
      0001_주간-스프린트/
        original/sprint.m4a
        chunks/                 ← 분석 완료 후 삭제
        transcripts/part_0001.txt …
        full_transcript.txt     ← 사이트 ‘전체 텍스트’
        analysis.json
        summary.txt
        project.json
    2026-08-28/
      0002_고객사-킥오프/
        …
```

- 날짜 폴더: `YYYY-MM-DD`
- 프로젝트 폴더: `{id:04d}_{slug}`
- DB `projects.date` = `2026-09-01` (인덱스). 목록/검색/삭제 모두 DB가 소스.

### 홈 화면

날짜 헤더 아래 프로젝트 행.

```
2026년 9월 1일
  주간 스프린트 회의     Part 4/11   전사 중
2026년 8월 28일
  고객사 킥오프          3시간 12분   완료
```

최신 날짜가 위. 같은 날 안에서는 최신 프로젝트가 위.

검색은 날짜를 가로질러 전체. 결과 행에 날짜 caption을 붙인다.

---

## 6. 사이트에서 꺼내 보기 · 검색

설정 페이지 없음. 키는 `.env`만.

| 경로 | 하는 일 |
|---|---|
| `/` | 날짜 그룹 목록. 검색창. 새 분석 |
| `/upload` | 파일 + 제목 → 즉시 처리 시작 |
| `/projects/:id` | 처리 중이면 Part 진행. 끝나면 전체 텍스트 / AI 분석 탭. 실패면 이어서 재시도 |
| `/search?q=` | 제목 + 전체 텍스트 + 요약 6필드. snippet 하이라이트. 클릭하면 해당 탭 |

복사 버튼으로 `full_transcript`를 클립보드에. 프로젝트 삭제는 Phase 4, 확인 모달.

검색 엔진: SQLite FTS5 + 한글 0건이면 LIKE 폴백. 벡터/RAG/채팅 없음.

---

## 7. 화면 (nas-note)

워드마크 `nas-note`. 톤은 그대로 (종이 `#F4F1EA`, 액센트 `#C45C26`, Pretendard).

빈 홈 카피: `아직 분석한 녹음이 없습니다` / `첫 녹음 올리기`.

건강 배너:

- Groq 키 없음: `.env`의 `GROQ_API_KEY`
- Gemini 키 없음: 전사는 되고 분석만 실패할 수 있음
- FFmpeg 없음: 분할 불가

상세 픽셀·카피는 `docs/SITE_DESIGN.md`. 목업 `design-preview/index.html`.

---

## 8. 파이프라인 상태

```
pending → splitting → transcribing → analyzing → done
                                              ↘ failed
```

청크: `pending → processing → done | failed`  
서버가 죽으면 processing은 pending으로 되돌리고 그 조각만 다시 STT.

진행률: 분할 5% · STT 5–85% · 분석 90% · 완료 100%. 폴링 2초.

완료 후 `chunks/` 삭제. `original/` + 텍스트 + 분석은 날짜 폴더에 남김.

---

## 9. 필요한 것

`.env` (지금 레포에 있음. 키만 붙여넣기):

```
GROQ_API_KEY=
GEMINI_API_KEY=
```

| 항목 | 어디서 |
|---|---|
| Groq 키 | https://console.groq.com/keys |
| Gemini 키 | https://aistudio.google.com/apikey |
| Python | 이 PC는 `py` (3.14). `python` 명령은 없음 |
| Node 20 | 설치됨 |
| FFmpeg | `winget install Gyan.FFmpeg` 후 새 터미널 |

없어도 됨: Redis, Docker, 벡터 DB, xAI 계정.

---

## 10. 개발 순서

0. 골격 + `/health`가 groq/gemini/ffmpeg 표시  
1. 업로드 → 날짜 폴더 → 24MB 분할 → Groq 순차 STT → 한 텍스트 병합 → 폴링 UI  
2. Gemini Pro 6필드 → 결과 탭 → chunks 삭제  
3. 날짜 그룹 목록 + FTS5 검색  
4. 삭제, 로그, 큐 대기  

재시도·상태 머신은 1에 포함.

---

## 11. 수락 기준

1. 제품명 사이트 전면이 `nas-note`
2. STT 호출이 `api.groq.com` + `whisper-large-v3` 뿐. xAI/Grok 코드 없음
3. 24MB 넘는 원본은 조각 STT 후 **하나의** 전체 텍스트로 보임
4. 홈이 날짜별로 묶임. 디스크도 `projects/YYYY-MM-DD/`
5. 끝난 프로젝트를 목록에서 열어 원문·요약을 바로 봄
6. 검색이 원문/요약을 찾음
7. 모델 기본값이 large-v3 / gemini-2.5-pro
8. `.env`에 키 두 개만 넣으면 동작
