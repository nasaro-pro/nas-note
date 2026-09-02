# nas-note

이 컴퓨터에서만 도는 사이트입니다. 주소는 **http://localhost:5173/** 입니다.

## 다른 노트북에서

1. GitHub에서 **Code → Download ZIP** 받아 압축을 풀거나, `git clone` 한다.
2. 폴더 안의 **`start.bat`을 더블클릭**한다.
3. 처음이면 Python / Node / FFmpeg를 알아서 설치한다. Wi-Fi가 필요하다.
4. 키가 없으면 창에서 물어본다. Enter로 건너뛰어도 사이트는 열린다.
5. 브라우저가 **http://localhost:5173/** 로 열린다.

끝낼 때는 `start.bat` 검은 창에서 아무 키나 누른다.

안 열리면 `start.bat`을 한 번 더 실행한다. 자세한 내용은 같은 폴더의 `start.log`를 본다.

## 키

키는 GitHub에 올리지 않는다. 이 노트북 폴더의 `.env`에만 둔다.

- Groq: https://console.groq.com/keys  (`gsk_` 로 시작)
- Gemini: https://aistudio.google.com/apikey

`start.bat`이 `.env`를 만들어 주거나, `.env.example`을 복사해 `.env`로 바꿔도 된다.

업로드·변환은 키가 있어야 한다. 화면만 보는 것은 키 없이도 된다.

## 올리지 않는 것

목업, 설계 문서, 녹음/영상, `.env`, `data/` 는 저장소에 넣지 않는다. 사이트 코드만 둔다.
