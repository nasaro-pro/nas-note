# nas-note

이 컴퓨터에서만 도는 사이트입니다. 주소는 **http://localhost:5173/** 입니다.

## 다른 노트북에서

PowerShell을 열고 아래 **한 줄**을 그대로 붙여넣는다. 폴더 만들기, 다운로드, 실행까지 한다.

```
New-Item -ItemType Directory -Force C:\nas-note | Out-Null; Set-Location C:\nas-note; if (-not (Test-Path .\nas-note\start.ps1)) { git clone https://github.com/nasaro-pro/nas-note.git }; Set-Location C:\nas-note\nas-note; git pull; powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

처음이면 Python / Node / FFmpeg를 설치하느라 몇 분 걸릴 수 있다. 끝나면 **http://localhost:5173/** 이 열린다. 안 열리면 주소창에 직접 넣는다.

끌 때는 `C:\nas-note\nas-note\stop.bat` 을 더블클릭한다.

### start.bat 이 차단되면

Windows가 GitHub에서 받은 파일을 인터넷 파일로 표시해서 막습니다.

1. `start.bat` **우클릭 → 속성**
2. 아래쪽 **차단 해제**에 체크 → **확인**
3. `start.bat`을 다시 더블클릭

속성 창에 차단 해제가 없으면 PowerShell을 열고 아래를 그대로 붙여넣는다. 폴더 경로는 압축 푼 위치로 바꾼다.

```
cd "C:\여기에\nas-note폴더"
Get-ChildItem -Recurse -File | Unblock-File
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

SmartScreen이 뜨면 **추가 정보 → 실행** 을 누른다.


## 키

키는 GitHub에 올리지 않는다. 이 노트북 폴더의 `.env`에만 둔다.

- Groq: https://console.groq.com/keys  (`gsk_` 로 시작)
- Gemini: https://aistudio.google.com/apikey

`start.bat`이 `.env`를 만들어 주거나, `.env.example`을 복사해 `.env`로 바꿔도 된다.

업로드·변환은 키가 있어야 한다. 화면만 보는 것은 키 없이도 된다.

## 올리지 않는 것

목업, 설계 문서, 녹음/영상, `.env`, `data/` 는 저장소에 넣지 않는다. 사이트 코드만 둔다.
