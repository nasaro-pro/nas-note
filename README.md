# nas-note

이 컴퓨터에서만 도는 사이트입니다. 주소는 **http://localhost:5173/** 입니다.

ZIP으로 받지 마세요. GitHub에서 `git clone`만 합니다. 폴더는 **바탕화면\nas-note** 에 생깁니다.

## 다른 노트북 — 이 한 줄만

PowerShell을 연 뒤 **아래 박스 안만** 복사합니다. `PS C:\...>` 는 넣지 않습니다.

처음부터 (예전 폴더 지우고 다시):

```
$d=[Environment]::GetFolderPath('Desktop'); $p=Join-Path $d 'nas-note'; Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue; git clone https://github.com/nasaro-pro/nas-note.git $p; if (Test-Path (Join-Path $p 'start.ps1')) { powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $p 'start.ps1') } else { Write-Host 'clone failed' }
```

이미 받아 둔 뒤 켜기만:

```
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path ([Environment]::GetFolderPath('Desktop')) 'nas-note\start.ps1')
```

처음이면 몇 분 걸릴 수 있습니다. 끝나면 브라우저가 열립니다. 안 열리면 **http://localhost:5173/** 을 주소창에 넣습니다.

끌 때:

```
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path ([Environment]::GetFolderPath('Desktop')) 'nas-note\stop.ps1')
```

## 키

키는 GitHub에 올리지 않습니다. 바탕화면 `nas-note\.env`에만 둡니다.

- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey
