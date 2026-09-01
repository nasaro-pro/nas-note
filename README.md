# nas-note

긴 녹음/영상을 올리면 Groq Whisper로 텍스트를 잇고, Gemini로 학습 노트를 만든 뒤 날짜별로 로컬에 쌓아 사이트에서 바로 찾고 본다.

## 다른 Windows PC에서 (GitHub clone 후)

1. 이 저장소를 받는다.
2. **`start.bat`을 더블클릭**한다.
   - Python / Node / FFmpeg가 있으면 건너뛴다.
   - 없으면 Wi-Fi로 winget 설치한다.
   - 패키지 설치 후 브라우저가 열린다.
   - 폴더가 바탕 화면·OneDrive·한글 경로여도 된다.
3. 그 PC에 `.env`가 없으면 키를 한 번만 물어본다. **키는 GitHub에 올리지 않는다.**

주소: http://localhost:5173/

끝낼 때는 `start.bat` 창에서 아무 키나 누르면 서버가 같이 꺼진다.

## 키 (.env)

이 컴퓨터의 키는 로컬 `.env`에만 있다. `.gitignore`로 커밋에서 빠진다.

다른 컴퓨터에서는 처음 실행 때 붙여넣기:

- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey

채팅·README·코드에 키를 다시 붙이지 말 것.

## 문서

| 파일 | 내용 |
|---|---|
| [SPEC.md](SPEC.md) | 설계·계획 총정리 |
| [docs/SITE_DESIGN.md](docs/SITE_DESIGN.md) | 화면 |
| [docs/API_GROQ_GEMINI.md](docs/API_GROQ_GEMINI.md) | Groq / Gemini |
