# nas-note

이 컴퓨터에서만 도는 사이트입니다. 주소는 **http://localhost:5173/** 입니다.

**ZIP으로 받지 마세요.** Windows가 `start.bat`을 차단합니다. **GitHub에서 `git clone`만** 합니다.

## 다른 노트북 — 이 한 줄

PowerShell을 연 뒤, **아래 박스 안만** 복사합니다. `PS C:\...>` 는 넣지 않습니다.

```
git clone https://github.com/nasaro-pro/nas-note.git C:\nas-note; powershell -NoProfile -ExecutionPolicy Bypass -File C:\nas-note\start.ps1
```

이미 `C:\nas-note`가 있으면 지우고 다시 할 때:

```
Remove-Item -Recurse -Force C:\nas-note -ErrorAction SilentlyContinue; git clone https://github.com/nasaro-pro/nas-note.git C:\nas-note; powershell -NoProfile -ExecutionPolicy Bypass -File C:\nas-note\start.ps1
```

`start.bat`은 쓰지 않아도 됩니다. clone 한 뒤 `start.ps1`을 바로 실행합니다.

처음이면 Python / Node 설치에 몇 분 걸릴 수 있습니다. 끝나면 **http://localhost:5173/** 이 열립니다.

끌 때는 `C:\nas-note\stop.ps1` 또는 `C:\nas-note\stop.bat` 을 실행합니다.

## 키

키는 GitHub에 올리지 않습니다. 이 PC의 `.env`에만 둡니다.

- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey

업로드는 키가 있어야 합니다. 화면만 보는 것은 키 없이도 됩니다.
