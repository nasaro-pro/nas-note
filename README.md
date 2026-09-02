# nas-note

이 컴퓨터에서만 도는 사이트입니다. 주소는 **http://localhost:5173/** 입니다.

Git이 없어도 됩니다. **빈 폴더**에서 아래 한 줄만 붙여넣으면 코드를 받고 사이트를 켭니다.

## 다른 노트북

1. 바탕화면에 빈 폴더를 만든다. (예: `새 폴더`)
2. 그 폴더를 연 다음, 빈 곳을 **Shift+우클릭 → PowerShell 창 열기**
3. **아래 박스 안만** 붙여넣는다. `PS C:\...>` 는 넣지 않는다.

```
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; iex (irm https://raw.githubusercontent.com/nasaro-pro/nas-note/main/bootstrap.ps1)
```

처음이면 몇 분 걸릴 수 있습니다. 끝나면 브라우저가 열리고 바로 쓰면 됩니다. 안 열리면 **http://localhost:5173/** 을 주소창에 넣습니다.

이미 코드가 있는 폴더에서 다시 켤 때도 같은 한 줄이면 됩니다.

끌 때 그 폴더에서:

```
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop.ps1
```

## 키

키는 GitHub에 올리지 않습니다. 그 폴더의 `.env`에만 둡니다.

- Groq: https://console.groq.com/keys
- Gemini: https://aistudio.google.com/apikey
