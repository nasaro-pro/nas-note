# 사이트 전체 디자인 스펙

구현 시 이 문서의 픽셀·카피·상태를 그대로 따른다. 클릭 가능한 목업은 `design-preview/index.html`이다. 기술 파이프라인은 `DESIGN.md`.

제품명 **nas-note**. 개인용 로컬 도구이므로 랜딩/온보딩/마케팅 히어로는 없다.

---

## 1. 제품 톤

긴 회의록을 **읽는 도구**다. 오디오 이퀄라이저, 네온, 대시보드 위젯을 쓰지 않는다.

- 종이 위에 잉크. 따뜻한 오프화이트 배경.
- 액센트는 녹음기/구리 느낌의 녹슨 오렌지 하나.
- 장식 그라데이션·그림자 과다·이모지 아이콘 금지.
- 한글 UI. 버튼은 동사로 끝낸다.

한 줄 카피: `긴 녹음을 올리면 텍스트와 요약까지 자동으로 끝납니다.`

---

## 2. 뷰포트 · 그리드

| 항목 | 값 |
|---|---|
| 우선 대상 | 데스크톱 1280×800 이상 |
| 최소 지원 | 960px. 그 이하는 Phase 4에서 단순 스택 |
| 앱 셸 | 전체 폭, 상단바 고정 |
| 콘텐츠 폭 | `min(1080px, 100% - 64px)`, 좌우 패딩 32px, 가운데 정렬 |
| 상단바 높이 | 56px |
| 섹션 간격 | 32px |
| 카드 내부 패딩 | 20px |
| 리스트 행 높이 | 72px |
| 모서리 | 8px (카드), 6px (버튼/인풋), 4px (뱃지) |
| 포커스 링 | `0 0 0 2px var(--bg), 0 0 0 4px var(--accent)` |

모바일 전용 네비/햄버거는 만들지 않는다.

---

## 3. 컬러 토큰

CSS 변수명과 hex를 코드에 그대로 쓴다.

```css
:root {
  --bg: #F4F1EA;
  --bg-elevated: #FFFcf7;
  --bg-muted: #EBE6DC;
  --ink: #1C1915;
  --ink-2: #5C574F;
  --ink-3: #8A847A;
  --line: #DDD6C8;
  --line-strong: #C9C0B0;
  --accent: #C45C26;
  --accent-hover: #A84B1C;
  --accent-soft: #F3E2D6;
  --success: #2F6B4F;
  --success-soft: #DCE8E1;
  --danger: #B42318;
  --danger-soft: #F8E2DF;
  --info: #2C5F8A;
  --info-soft: #DCE7F0;
  --warning: #9A6700;
  --warning-soft: #F5EBD3;
}
```

상태 색은 뱃지·배너·Part 점에만 쓴다. 본문 텍스트는 `--ink` / `--ink-2`만.

---

## 4. 타이포

폰트: **Pretendard** (CDN 또는 npm `pretendard`). 폴백 `system-ui, sans-serif`.

숫자·Part 번호·파일 크기: `ui-monospace, "Cascadia Mono", "Menlo", monospace`.

| 토큰 | 크기 / 행간 / 두께 | 용도 |
|---|---|---|
| display | 28px / 36px / 650 | 페이지 제목 1개만 |
| title | 20px / 28px / 600 | 프로젝트 제목, 분석 섹션 |
| body | 15px / 24px / 400 | UI 본문 |
| transcript | 16px / 28px / 400 | 전체 텍스트 탭. 읽기용 |
| caption | 13px / 20px / 400 | 메타, 힌트 |
| overline | 11px / 16px / 600, letter-spacing 0.06em, 대문자 아님 | 섹션 라벨 |
| button | 14px / 20px / 600 | 버튼 |

본문 최대 너비(결과 텍스트): 720px. 분석 섹션은 콘텐츠 폭 전체(1080).

---

## 5. 아이콘

이모지 금지. 16×16 또는 20×20 스트로크 아이콘, 선 1.75px, currentColor.

필요 세트 (Lucide 이름 기준, 실제 구현은 같은 패스의 SVG):

| 이름 | 사용 |
|---|---|
| `plus` | 새 분석 |
| `search` | 검색 필드 |
| `upload` | 드롭존 |
| `file-audio` | 파일 메타 |
| `copy` | 텍스트 복사 |
| `check` | 완료 Part, 복사 완료 |
| `loader` | 처리 중 (CSS로 천천히 회전) |
| `circle` | 대기 Part |
| `x-circle` | 실패 |
| `trash-2` | 삭제 (Phase 4) |
| `play` | 재시도 (삼각형 아님. `rotate-ccw` 사용) |
| `rotate-ccw` | 이어서 재시도 |
| `arrow-left` | 목록으로 |

---

## 6. 컴포넌트

### 6.1 상단바

```
[ nas-note ]                    [ 검색 ………… ]     [ 새 분석 ]
```

- 배경 `--bg-elevated`, 하단 보더 `--line`.
| 워드마크: 15px/600 `--ink`. 클릭 시 `/`. 텍스트 `nas-note`.
- 검색: 너비 280px, 높이 36px, 왼쪽 검색 아이콘, placeholder `프로젝트 · 텍스트 · 요약 검색`. Enter 시 `/search?q=`.
- `새 분석`: Primary 버튼, 높이 36px, 이동 `/upload`.
- 상단바 검색은 홈·검색·결과에서만 노출. 업로드·처리 화면에서는 숨기고 왼쪽 `목록으로`.

### 6.2 버튼

| variant | 배경 | 글자 | 테두리 | 높이 |
|---|---|---|---|---|
| primary | `--accent` | white | none | 36px, 좌우 14px |
| secondary | transparent | `--ink` | `--line-strong` | 36px |
| ghost | transparent | `--ink-2` | none | 36px |
| danger | `--danger` | white | none | 36px |

disabled: opacity 0.45, pointer-events none.
hover primary: `--accent-hover`.
로딩: 텍스트 대신 스피너 + `처리 중`. 너비는 기존 라벨과 같게 유지.

### 6.3 뱃지 (status)

높이 22px, 패딩 0 8px, 12px/600, radius 4px.

| status | 라벨 | 배경 / 글자 |
|---|---|---|
| pending | 대기 | `--bg-muted` / `--ink-2` |
| splitting | 분할 중 | `--info-soft` / `--info` |
| transcribing | 전사 중 | `--info-soft` / `--info` |
| analyzing | 분석 중 | `--warning-soft` / `--warning` |
| done | 완료 | `--success-soft` / `--success` |
| failed | 실패 | `--danger-soft` / `--danger` |
| queued | 대기열 | `--bg-muted` / `--ink-2` |

### 6.4 Part 행

왼쪽 20px 원형 상태점, 가운데 `Part 08` + caption `23.1 MB`, 오른쪽 상태 텍스트.

| 상태 | 점 색 | 오른쪽 |
|---|---|---|
| pending | `--line-strong` | 대기 |
| processing | `--accent`, 펄스 | 처리 중 |
| done | `--success` | 완료 |
| failed | `--danger` | 실패 |

처리 중인 행만 `--accent-soft` 배경.

### 6.5 프로젝트 행 (홈 목록)

전체 행 클릭. hover `--bg-muted`.

```
제목 (title 20px)                          3시간 12분
2026.09.01  ·  meeting.mp3  ·  412 MB      [완료]
```

제목 1줄 truncate. duration은 우측, caption 모노.

### 6.6 배너

페이지 콘텐츠 최상단, radius 8px, 패딩 14px 16px, 왼쪽 3px 액센트 바.

| tone | 사용 |
|---|---|
| danger | 처리 실패, API 키 없음 |
| warning | FFmpeg 없음 |
| info | 큐에서 대기 중 |

### 6.7 탭

결과 화면 전용. 하단 2px 인디케이터. 활성 `--accent` + `--ink`. 비활성 `--ink-3`. 높이 40px.

- 전체 텍스트
- AI 분석

### 6.8 분석 섹션 카드

overline 라벨 + title이 아니라 overline만 + 본문. 빈 배열은 본문 자리에 `이 녹음에서 확인된 항목이 없습니다.` `--ink-3`.

순서 고정:

1. 전체 요약
2. 핵심 내용 (불릿)
3. 상세 요약
4. 결정 사항 (불릿)
5. 할 일 (체크 없는 불릿. 체크박스로 완료 처리하지 않음 — 로컬 TODO 앱이 아님)
6. 중요 내용 (불릿)

### 6.9 모달 (삭제 확인, Phase 4)

폭 420px, 중앙. 타이틀 `이 프로젝트를 삭제할까요?` 본문 `원본 파일, 텍스트, 분석이 디스크에서 삭제됩니다.` 버튼 `취소` secondary + `삭제` danger.

### 6.10 토스트

우하단, 3초. 복사 완료만. `텍스트를 복사했습니다.`

---

## 7. 라우트 · 정보구조

| 경로 | 화면 | 상단바 |
|---|---|---|
| `/` | 홈 | 워드마크 + 검색 + 새 분석 |
| `/upload` | 업로드 | 목록으로 + 워드마크 |
| `/projects/:id` | 처리 또는 결과 또는 실패. 상태 따라 같은 라우트 | 처리 중: 목록으로. 완료: 검색 + 새 분석 |
| `/search?q=` | 검색 결과 | 워드마크 + 검색(쿼리 유지) + 새 분석 |

설정 페이지 없음. API 키는 `.env`만.

---

## 8. 화면별 상세

각 화면은 **레이아웃 / 카피 / 상태 / 동작**을 적는다.

### 8.1 홈 — 프로젝트 없음

**레이아웃**

```
[상단바]
콘텐츠:
  왼쪽: display 제목 + caption 한 줄
  오른쪽 없음
  중앙 빈 상태 블록 (상단 제목 아래 64px)
    아이콘 file-audio 32px
    title: 아직 분석한 녹음이 없습니다
    body: 3~4시간 파일이어도 업로드하면 분할, 전사, 요약까지 자동으로 진행됩니다.
    primary: 첫 녹음 올리기  → /upload
```

제목: `nas-note`  
서브: `긴 녹음을 올리면 텍스트와 요약까지 자동으로 끝납니다.`

건강 배너 (해당될 때만, 제목 아래):

- FFmpeg 없음: warning `이 컴퓨터에 FFmpeg가 없습니다. 분할을 위해 설치가 필요합니다.`
- `GROQ_API_KEY` 없음: danger `Groq Whisper 키가 없습니다. .env의 GROQ_API_KEY를 확인하세요.`
- `GEMINI_API_KEY` 없음: danger `Gemini 키가 없습니다. 전사는 되지만 분석은 실패합니다.`
- 둘 다 없음: 배너 두 줄.

키가 없어도 업로드 화면 진입은 가능. 시작 버튼은 서버가 503을 주면 그 메시지를 업로드 화면에 표시.

### 8.2 홈 — 목록 있음 (날짜 그룹)

제목 행 오른쪽 작은 caption: `n개 프로젝트`.

목록은 **업로드 날짜(`YYYY-MM-DD`)로 묶는다**. 최신 날짜가 위.

```
2026년 9월 1일                          overline
  [프로젝트 행]
2026년 8월 28일
  [프로젝트 행]
```

날짜 헤더는 카드 밖, 13px/600 `--ink-2`, 섹션 간격 위 28px (첫 그룹은 0).

한 날짜의 행들은 카드 1개 안에. 같은 날 안에서는 최신 id가 위.

행 클릭 → `/projects/:id`.

진행 중이면 오른쪽 duration 대신 `Part 4/11` 모노.

### 8.3 업로드

제목: `새 분석`  
서브: `MP3, WAV, M4A, MP4. 업로드 이후 개입 없이 끝까지 진행합니다.`

1. 드롭존  
   - 높이 240px, 점선 2px `--line-strong`, radius 8px, 배경 `--bg-elevated`.  
   - dragover: 테두리 `--accent`, 배경 `--accent-soft`.  
   - 카피: `파일을 여기에 놓거나 클릭해서 선택` / caption `최대 용량 제한 없음. 24MB 넘으면 자동 분할.`  
   - input accept: `.mp3,.wav,.m4a,.mp4`.

2. 파일 선택됨  
   - 드롭존 대신 파일 카드: 파일명, 크기(MB, 소수 1자리), duration은 클라에서 못 구하면 생략. `다른 파일` ghost 버튼.

3. 제목 필드  
   - 라벨 `프로젝트 제목`  
   - 기본값: 확장자 제거한 파일명. 사용자가 수정 가능.  
   - 빈 제목이면 파일명 사용.  
   - 높이 40px, 전체 폭 최대 560px.

4. Primary `분석 시작` — 파일 없으면 disabled.  
   제출 중 버튼 로딩. 성공 시 `/projects/:id`로 replace.

에러:

- 확장자 거부: 드롭존 아래 danger 텍스트 `MP3, WAV, M4A, MP4만 올릴 수 있습니다.`
- 서버 400/503: 같은 위치.

진행 중 안내 없음. 시작 누르면 바로 처리 화면.

### 8.4 처리 중 (`status` = pending | splitting | transcribing | analyzing)

제목: 프로젝트 title.  
서브: 상태에 따라 한 줄.

| status | 서브 카피 |
|---|---|
| pending | 대기열에 있습니다. 앞선 작업이 끝나면 시작합니다. |
| splitting | 파일을 24MB 기준으로 나누고 있습니다. |
| transcribing | 조각을 순서대로 텍스트로 옮기고 있습니다. |
| analyzing | 전체 텍스트를 분석하고 있습니다. |

**프로그레스**

- 트랙 높이 4px, `--bg-muted`, 채움 `--accent`.  
- 오른쪽 숫자 `42%` 13px 모노 `--ink-2`.  
- percent 규칙은 `DESIGN.md` 11장.

**Part 리스트**

- splitting/pending이면 리스트 숨기고 caption `분할이 끝나면 Part 목록이 표시됩니다.`
- transcribing 이후 표시.
- analyzing이면 모든 Part는 완료로 두고, 프로그레스만 90%.

폴링: 2초. `done`이면 같은 URL에서 결과 화면으로 전환 (리다이렉트 없음). `failed`면 8.5.

페이지를 떠나도 처리는 계속. 안내 caption: `이 창을 닫아도 처리는 계속됩니다.`

### 8.5 실패

배너 danger: `{error_message}` 예 `Part 0004 전사에 실패했습니다.`

primary `이어서 재시도`. secondary 없음. ghost `목록으로`.

Part 리스트는 실패 행까지 보여 준다. 실패한 행 오른쪽에 `실패`.

분석 단계 실패면 배너 `분석에 실패했습니다. 텍스트는 저장되어 있습니다.` 버튼 같은 `이어서 재시도` — 서버가 Gemini만 다시 돌린다.

텍스트가 이미 있으면 탭 `저장된 텍스트 보기`로 전체 텍스트를 먼저 볼 수 있다 (분석만 실패한 경우). STT 실패면 이 링크 없음.

### 8.6 결과 — 전체 텍스트 탭

헤더:

```
제목                              [복사]
날짜 · 길이 · 원본 파일명           [완료]
탭: 전체 텍스트 | AI 분석
```

텍스트 영역: `--bg-elevated`, 패딩 28px 32px, 폭 100% 중 내부 문단 max 720px. `white-space: pre-wrap`. 화자 프리픽스 `화자 1:` 은 600 웨이트.

복사: `full_transcript` 클립보드. 토스트.

삭제(Phase 4): 헤더 더보기 메뉴 아니고, 페이지 맨 아래 ghost danger `프로젝트 삭제`.

### 8.7 결과 — AI 분석 탭

6개 섹션을 위에서 아래로. 섹션 사이 32px. 카드 배경 없이 보더-탑만 (`--line`). 첫 섹션은 보더 없음.

불릿: `–` 문자 또는 8px 사각 점 `--accent`. 번호 매기지 않음.

할 일 항목 예시 카피 스타일: `배포 일정을 금요일로 확정하고 슬랙에 공지한다.` 명령형.

### 8.8 검색 결과

제목: `‘배포 일정’ 검색 결과`  
서브: `n건`

결과 행:

```
프로젝트 제목                         [완료]
transcript  ·  ...배포 일정은 금요일...
```

`source` 라벨: `원문` | `분석` | `제목`. caption `--ink-3`.

snippet은 전후 40자, 매칭어 `background: var(--accent-soft)`.

0건: `일치하는 내용이 없습니다.` + `검색어를 짧게 바꿔 보세요.` (한글 FTS 한계 힌트는 넣지 않음. 이미 LIKE 폴백이 있음.)

클릭 → `/projects/:id`. 분석 히트면 분석 탭을 연 상태로 (`?tab=analysis`).

### 8.9 전역 에러

API 다운: 홈 배너 `백엔드에 연결할 수 없습니다. uvicorn이 켜져 있는지 확인하세요.`

404 프로젝트: `이 프로젝트를 찾을 수 없습니다.` + `목록으로`.

---

## 9. 마이크로카피 전체 목록

| ID | 한국어 |
|---|---|
| app.name | nas-note |
| app.tagline | 긴 녹음을 올리면 텍스트와 요약까지 자동으로 끝납니다. |
| nav.new | 새 분석 |
| nav.back | 목록으로 |
| search.placeholder | 프로젝트 · 텍스트 · 요약 검색 |
| home.empty.title | 아직 분석한 녹음이 없습니다 |
| home.empty.body | 3~4시간 파일이어도 업로드하면 분할, 전사, 요약까지 자동으로 진행됩니다. |
| home.empty.cta | 첫 녹음 올리기 |
| upload.title | 새 분석 |
| upload.sub | MP3, WAV, M4A, MP4. 업로드 이후 개입 없이 끝까지 진행합니다. |
| upload.drop | 파일을 여기에 놓거나 클릭해서 선택 |
| upload.hint | 최대 용량 제한 없음. 24MB 넘으면 자동 분할. |
| upload.titleLabel | 프로젝트 제목 |
| upload.submit | 분석 시작 |
| upload.otherFile | 다른 파일 |
| proc.keepOpen | 이 창을 닫아도 처리는 계속됩니다. |
| proc.retry | 이어서 재시도 |
| result.copy | 복사 |
| result.tab.text | 전체 텍스트 |
| result.tab.analysis | AI 분석 |
| analysis.empty | 이 녹음에서 확인된 항목이 없습니다. |
| analysis.s1 | 전체 요약 |
| analysis.s2 | 핵심 내용 |
| analysis.s3 | 상세 요약 |
| analysis.s4 | 결정 사항 |
| analysis.s5 | 할 일 |
| analysis.s6 | 중요 내용 |
| fail.stt | Part {n} 전사에 실패했습니다. |
| fail.gemini | 분석에 실패했습니다. 텍스트는 저장되어 있습니다. |
| toast.copied | 텍스트를 복사했습니다. |
| delete.title | 이 프로젝트를 삭제할까요? |
| delete.body | 원본 파일, 텍스트, 분석이 디스크에서 삭제됩니다. |
| delete.confirm | 삭제 |
| delete.cancel | 취소 |

---

## 10. 모션

최소화. 허용:

- 버튼 hover 120ms background
- 프로그레스 바 width 400ms linear (폴링 점프 완화)
- 처리 중 점 opacity 1 ↔ 0.4, 1.2s ease
- 스피너 1s linear rotate
- 토스트 아래→위 160ms

페이지 전환 애니메이션 없음.

---

## 11. 접근성

- 드롭존은 `button` 또는 `label` + hidden file input. 키보드 Enter로 파일창.
- 폴링 중 `aria-live="polite"` 로 상태 문구만 갱신 (Part 리스트 전부 읽지 않음).
- 색만으로 상태 구분 금지. 뱃지 텍스트 필수.
- 포커스 링 4장 규칙.

---

## 12. 프론트 파일 매핑 (구현 시)

```
frontend/src/
  styles/tokens.css      # 3장 변수
  components/
    TopBar.tsx
    Button.tsx
    Badge.tsx
    Banner.tsx
    PartList.tsx
    ProjectRow.tsx
    Dropzone.tsx
    AnalysisSections.tsx
  pages/
    HomePage.tsx
    UploadPage.tsx
    ProjectPage.tsx      # 처리/실패/결과 분기
    SearchPage.tsx
```

컴포넌트에 하드코딩 hex 금지. `tokens.css`만.

---

## 13. 목업과 구현의 관계

`design-preview/index.html`은 이 문서의 시각 원본이다. React 구현이 목업과 어긋나면 목업을 우선한다. 카피가 다르면 이 문서 9장을 우선한다.
