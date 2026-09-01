# 필요한 것 전부

개발을 시작하기 전에 이 목록을 채운다. 하나라도 빠지면 파이프라인이 해당 단계에서 멈춘다.

---

## 1. 사람 / 계정

| 항목 | 어디서 | 필수 | 용도 |
|---|---|---|---|
| Groq 계정 | https://console.groq.com | 필수 | Whisper STT |
| `GROQ_API_KEY` | https://console.groq.com/keys | 필수 | `whisper-large-v3` |
| Google AI Studio 계정 | https://aistudio.google.com | 필수 | Gemini |
| `GEMINI_API_KEY` | AI Studio → Get API key | 필수 | `gemini-2.5-pro` 분석 |
| Groq 사용량 | 무료 한도 또는 개발자 플랜 | 3~4시간이면 유료 한도 확인 | large-v3 ≈ $0.111/시간 |
| Gemini 결제 | 사용량에 따라 | Pro는 Flash보다 비쌈. 2~3파일이면 감당 | |

키를 GitHub·채팅·프론트 코드에 붙이지 않는다. `.env`만.

---

## 2. 로컬 소프트웨어

| 항목 | 버전 | 확인 명령 (PowerShell) | 용도 |
|---|---|---|---|
| Windows 10/11 | 현재 머신 | — | 개발 OS |
| Python | 3.12+ | `py --version` 또는 `python --version` | FastAPI 백엔드. 이 PC는 `python`이 PATH에 없고 `py` 런처로 실행됨 |
| pip | Python과 함께 | `pip --version` | 패키지 |
| Node.js | 20 LTS+ | `node --version` | Vite + React |
| npm | Node와 함께 | `npm --version` | 프론트 패키지 |
| FFmpeg | 6+ 권장 | `ffmpeg -version` | 분할, duration, 재인코딩 |
| ffprobe | FFmpeg와 함께 | `ffprobe -version` | 길이·포맷 |
| Git | 2+ | `git --version` | 버전관리 (원하면) |
| 브라우저 | Chrome/Edge | — | 앱 UI |

### FFmpeg 설치 (Windows)

1. https://www.gyan.dev/ffmpeg/builds/ 또는 `winget install Gyan.FFmpeg`
2. 설치 후 **새 터미널**에서 `ffmpeg -version`
3. PATH에 없으면 백엔드 `/health`가 degraded, 업로드 503

Chocolatey: `choco install ffmpeg`.

---

## 3. Python 패키지 (backend)

```
fastapi
uvicorn[standard]
python-multipart      # 파일 업로드
groq                  # Whisper STT 공식 SDK
httpx                 # 필요 시 REST
google-genai          # Gemini 공식 SDK
python-dotenv         # .env
aiosqlite             # SQLite async
pydantic-settings     # config
```

선택: `pytest`, `ruff`.

`requirements.txt`로 고정. 가상환경 `backend/.venv`.

---

## 4. Node 패키지 (frontend)

```
react
react-dom
react-router-dom
typescript
vite
@types/react
@types/react-dom
```

CSS는 직접. Tailwind는 쓰지 않는다 (디자인 토큰이 이미 정해짐).

아이콘: `lucide-react` 허용.

---

## 5. 환경 변수

파일: 레포 루트 `.env` (gitignore). 템플릿 `.env.example`.

```
GROQ_API_KEY=
GEMINI_API_KEY=
GROQ_STT_MODEL=whisper-large-v3
GEMINI_MODEL=gemini-2.5-pro
DATA_DIR=./data
HOST=127.0.0.1
PORT=8000
```

| 변수 | 없으면 |
|---|---|
| GROQ_API_KEY | 업로드 503, 홈 배너 |
| GEMINI_API_KEY | STT까지는 가능, analyzing에서 failed |
| GEMINI_MODEL | 기본 `gemini-2.5-pro` |
| GROQ_STT_MODEL | 기본 `whisper-large-v3` |
| DATA_DIR | 기본 `./data` |
| HOST/PORT | 127.0.0.1:8000 |

프론트는 키를 읽지 않는다. `VITE_` 키를 만들지 않는다.

---

## 6. 디스크 · 네트워크

| 항목 | 기준 |
|---|---|
| 여유 공간 | 처리할 파일 크기의 **3배** (원본 + 청크 + 여유). 3시간 200MB면 600MB+ |
| `DATA_DIR` 쓰기 권한 | OneDrive 경로여도 동작해야 함. 파일 잠김이 있으면 로컬 폴더로 옮길 것 |
| 아웃바운드 HTTPS | `api.groq.com`, `generativelanguage.googleapis.com` |
| 방화벽 | 로컬 8000, 5173 루프백 |
| 업로드 시간 | 수백 MB는 같은 PC 복사라 수 초~수십 초 |

OneDrive 바탕화면 워크스페이스는 동기화 중 파일 잠금이 날 수 있다. 문제가 나면 `DATA_DIR`을 `C:\audio-ai-data`처럼 동기화 밖 경로로 둔다.

---

## 7. 외부 API 한도 (개발 전 인지)

### Groq Whisper

| 항목 | 값 |
|---|---|
| URL | `POST https://api.groq.com/openai/v1/audio/transcriptions` |
| 인증 | `GROQ_API_KEY` |
| 모델 | `whisper-large-v3` |
| 파일 한도 | 무료 25MB 직접 업로드 (우리는 24MB) |
| 한국어 | `language=ko` |
| 화자 분리 | 없음 |

### Gemini

| 항목 | 값 |
|---|---|
| 모델 | `gemini-2.5-pro` |
| SDK | `google-genai` |
| 출력 | JSON schema 6필드 |
| 입력 | 전체 transcript 또는 MAP 조각 |

키 발급 직후 할당량 0 / 결제 미등록이면 429 또는 403. 재시도 정책에 포함.

---

## 8. 샘플 데이터 (개발·수동 테스트)

| 파일 | 용도 |
|---|---|
| 30초 이하 짧은 MP3 (< 24MB) | 분할 스킵 경로 |
| 의도적으로 큰 WAV 또는 낮은 bitrate가 아닌 파일 > 24MB | 분할 경로. 없으면 FFmpeg로 무음 생성 |
| 한국어 회의 1~3분 | STT 품질 육안 확인 |
| 빈 파일 / txt 위장 | 400 에러 확인 |

무음 테스트 파일 생성 예:

```
ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 3600 -b:a 192k test-1h.mp3
```

1시간 192kbps면 약 86MB → 분할이 일어난다.

---

## 9. 개발 시 켜 두는 프로세스

동시에 2개:

1. `uvicorn` 백엔드 `127.0.0.1:8000`
2. `npm run dev` 프론트 `localhost:5173` (proxy `/api` → 8000)

브라우저는 **5173**만 연다. 8000을 직접 열어 CORS를 우회하지 않는다 (Vite proxy 사용).

---

## 10. 없어도 되는 것 (명시)

- Redis, Celery, Docker, PostgreSQL, S3
- 도메인, HTTPS 인증서, nginx
- 벡터 DB, LangChain, RAG 프레임워크
- Figma 계정 (목업 HTML이 디자인 원본)
- GPU, 로컬 Whisper 모델

---

## 11. 시작 전 체크리스트

인쇄해서 체크.

- [ ] Python 3.12+ (`py --version`)
- [ ] Node 20+
- [ ] `ffmpeg -version` 성공
- [ ] `ffprobe -version` 성공
- [ ] Groq 키를 `.env`의 `GROQ_API_KEY`에 넣음 (https://console.groq.com/keys)
- [ ] Gemini 키를 `.env`의 `GEMINI_API_KEY`에 넣음 (https://aistudio.google.com/apikey)
- [ ] 콘솔에서 키로 각각 1회 테스트 호출 성공 (아래)
- [ ] 디스크 여유 1GB 이상
- [ ] 짧은 한국어 mp3 하나 준비

### 키 스모크 테스트

Groq Whisper (짧은 파일):

```
curl -X POST https://api.groq.com/openai/v1/audio/transcriptions ^
  -H "Authorization: Bearer %GROQ_API_KEY%" ^
  -F model=whisper-large-v3 ^
  -F language=ko ^
  -F file=@short.mp3
```

응답 JSON에 `text`가 있으면 OK.

Gemini:

```
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent" ^
  -H "x-goog-api-key: %GEMINI_API_KEY%" ^
  -H "Content-Type: application/json" ^
  -d "{\"contents\":[{\"parts\":[{\"text\":\"ping\"}]}]}"
```

`candidates`가 있으면 OK.
