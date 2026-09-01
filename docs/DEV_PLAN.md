# 개발 과정 계획서

스펙 원본: `SPEC.md`. 화면: `docs/SITE_DESIGN.md`. 필요물: `docs/REQUIREMENTS.md`. API: `docs/API_GROQ_GEMINI.md`. 목업: `design-preview/index.html`.

한 사람 기준. 하루에 2~4시간 잡으면 Phase 1이 가장 길다.

---

## 0. 작업 원칙

1. 목업과 토큰을 먼저 맞추고 API를 붙인다. 스타일을 마지막에 갈아엎지 않는다.
2. 워커·status·재시도는 Phase 1에 넣는다.
3. 실제 Groq/Gemini 호출은 짧은 파일로만. 분할 로직은 FFmpeg 무음 파일로.
4. 커밋은 사용자가 요청할 때만. 이 계획서는 커밋 단위 제안만 한다.

---

## 1. 일정 개요

| 단계 | 내용 | 예상 |
|---|---|---|
| 0 | 환경, 키 스모크, 레포 골격 | 0.5일 |
| 1 | 업로드·날짜 폴더·24MB 분할·워커·Groq Whisper·한 텍스트 병합·폴링 UI | 2~3일 |
| 2 | Gemini 6필드·map-reduce·결과 탭·청크 삭제 | 1~1.5일 |
| 3 | 목록·검색 FTS5 | 0.5~1일 |
| 4 | 삭제·로그·큐 UI·가장자리 | 0.5~1일 |

합계 약 5~7일. 막히면 STT/Gemini를 mock으로 두고 UI를 먼저 끝내는 우회가 있다 (1-B).

---

## 2. Phase 0 — 착수 전

체크리스트는 `REQUIREMENTS.md` 11장. 전부 체크된 뒤에 Phase 1.

산출물:

```
/
  .gitignore
  .env.example
  README.md
  DESIGN.md
  docs/
  design-preview/
  backend/
    requirements.txt
    main.py          # /health 만
  frontend/
    package.json
    vite.config.ts   # proxy /api
    src/main.tsx     # 빈 페이지 + 토큰 CSS
```

`GET /health`가 ffmpeg/키/db를 돌려주고, 프론트 홈이 배너를 보여 주면 Phase 0 완료.

제안 커밋: `chore: scaffold app with health check`.

---

## 3. Phase 1 — 핵심 파이프라인

순서 고정. 앞 항목이 끝나야 다음.

### 1-1 DB

- `database/db.py` 초기화, WAL, 마이그레이션 SQL 한 파일
- 테이블: projects, chunks, transcripts (analyses는 빈 파일만 만들어 둬도 됨)
- 완료: Python으로 insert/select 한 번씩

### 1-2 저장소

- `storage/project_storage.py`
- `DATA_DIR/projects/{id:04d}_{date}_{slug}/original/`
- 업로드 파일을 여기로 복사

### 1-3 업로드 API

- `POST /api/projects` multipart
- 201 `{id, status:"pending"}`
- 아직 워커 없이 DB+파일만

### 1-4 프론트 업로드 + 홈 골격

- 목업과 같은 드롭존, 제목 필드
- 성공 시 `/projects/:id` (빈 처리 화면)

### 1-5 splitter

- ffprobe duration/size
- 24MB 이하 → part_0001
- 초과 → 시간 분할, 재검사, 마지막 이등분
- 단위 테스트: 가짜 크기 또는 실제 무음 1시간 mp3
- 완료: `chunks/`에 part 파일 + chunks 행

### 1-6 워커

- lifespan `asyncio.Queue` + 단일 루프
- 시작 시 processing 롤백, 미완료 프로젝트 requeue
- status: pending → splitting → transcribing
- 이 시점 STT는 mock (`"[mock] part N"`) 가능

### 1-7 Groq Whisper 연결

- `stt_service.py` — `whisper-large-v3`, `GROQ_API_KEY`
- 재시도 3회
- 짧은 실음성 1회 성공 후 워커에 연결
- 조각 txt를 `full_transcript.txt`로 이어붙임
- done skip

### 1-8 병합 + status API

- `full_transcript.txt`
- `GET /api/projects/{id}/status`
- 프론트 2초 폴링, Part 리스트, percent 바, 실패 배너+재시도 버튼
- `POST /api/projects/{id}/retry`

**Phase 1 완료 조건** (`DESIGN.md` 19장 1~5)

- 24MB 이하가 자동으로 텍스트까지
- 초과 파일이 part_0001… 이고 모두 ≤ 24MB
- 폴링으로 Part 상태 갱신
- 서버 강제 종료 후 재시작해도 done Part skip
- 3회 실패 → failed, retry 시 그 Part부터

제안 커밋 단위: db / upload / splitter / worker+mock-stt / groq / polling-ui.

---

## 4. Phase 2 — Gemini

### 2-1 schema + 단일 호출

- 짧은 transcript로 6필드 JSON 저장
- 결과 화면 분석 탭 목업과 동일 레이아웃

### 2-2 100k 분기 + map-reduce

- 긴 문자열 fixture로 MAP/REDUCE 단위 테스트 (과금 없이)
- 실호출은 짧은 것 1회 + 필요 시 한 번만 긴 것

### 2-3 결과 UI

- 텍스트 탭 / 분석 탭
- 복사 토스트
- analyzing 중 90% 표시 후 전환

### 2-4 정리

- done 시 `chunks/` `work/` 삭제
- original 유지

**완료 조건:** 긴/짧은 모두 6필드. done 후 chunks 없음.

---

### 3 — 목록 · 검색

- 홈을 **날짜 그룹**으로
- 디스크 `projects/YYYY-MM-DD/{id}_{slug}/`
- FTS 트리거
- `GET /api/search?q=`
- 검색 페이지, snippet 하이라이트
- MATCH 0 → LIKE 폴백

**완료 조건:** 끝난 프로젝트 제목/원문/요약에서 단어가 찾아진다.

---

## 6. Phase 4 — 안정성

- DELETE 프로젝트 + 확인 모달
- 원본만 삭제 (optional)
- `DATA_DIR/logs/app.log`
- 큐에 2건 이상일 때 두 번째가 `대기열에 있습니다`
- 404 페이지

---

## 7. 우회 경로 (키/과금이 늦을 때)

```
Phase 0 → 프론트 전 페이지를 목업 데이터로 구현
        → splitter + worker + mock STT/Gemini
        → 키 도착 시 mock 한 줄만 실제 서비스로 교체
```

UI 승인과 파이프라인 승인을 분리할 수 있다.

---

## 8. 일일 검증 루틴

새 기능마다:

1. `/health` 200
2. 짧은 mp3 1개 업로드 → 처리 화면 Part 갱신
3. 완료 후 텍스트 탭에 글자 존재
4. (Phase 2+) 분석 6섹션 렌더
5. 서버 재시작 → 목록에 프로젝트 유지

브라우저에서 목업이 아니라 **5173 앱**을 클릭한다.

---

## 9. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| OneDrive 파일 잠금 | DATA_DIR을 로컬 디스크로 |
| Groq 요청 형식 | 공식 SDK `groq` + 짧은 파일로 먼저 검증 |
| 한글 FTS 0건 | LIKE 폴백 |
| Gemini JSON 깨짐 | schema 강제 + 재시도 |
| 3시간 파일로 개발 | 금지. 무음 1h는 분할만, STT는 30초 |
| 25MB 넘는 청크 | assert, splitter 버그로 간주 |
| 키를 프론트에 넣음 | 코드리뷰에서 탈락 |

---

## 10. 바로 다음에 할 일 (구현 시작 시)

1. Phase 0 골격 + health
2. 프론트 토큰 CSS를 목업에서 이식, 라우트 4개 빈 페이지
3. 업로드 API + 드롭존
4. splitter
5. 워커 + Groq Whisper → 한 텍스트

이 문서를 닫고 코드 작업을 시작할 때는 “Phase 0부터 구현”이라고 지시하면 된다.
