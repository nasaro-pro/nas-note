import { useState } from "react";

const HIDE_KEY = "nas-note.setupGuide.hideForever";

export function SetupGuide() {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(HIDE_KEY) !== "1";
    } catch {
      return true;
    }
  });

  if (!open) return null;

  function hideForever() {
    try {
      localStorage.setItem(HIDE_KEY, "1");
    } catch {
      /* ignore quota / private mode */
    }
    setOpen(false);
  }

  return (
    <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="setup-guide-title">
      <div className="modal wide">
        <h2 id="setup-guide-title">처음 한 번만 보면 됩니다</h2>
        <p className="lead">
          이 앱은 이 컴퓨터에서만 돌아갑니다. 키는 브라우저가 아니라 프로젝트 폴더의 <code>.env</code>에
          넣습니다. Whisper는 xAI <strong>Grok이 아닙니다</strong>. Groq 클라우드 키(<code>gsk_</code>)입니다.
        </p>

        <p className="guide-h">다른 컴퓨터에서</p>
        <p>
          ZIP은 받지 마세요. GitHub에서 <code>git clone</code> 한 뒤{" "}
          <code>powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1</code> 만 실행합니다.
          사이트는 <code>http://localhost:5173/</code> 입니다.
        </p>

        <p className="guide-h">1. Cursor / VS Code에서 .env 만들기</p>
        <ol>
          <li>
            왼쪽 파일 탐색기에서 <strong>start.bat이 있는 폴더</strong>(프로젝트 루트)를 엽니다.
          </li>
          <li>
            빈 곳을 우클릭 → 새 파일. 이름을 정확히 <code>.env</code>로 저장합니다. 앞에 점(<code>.</code>)이
            꼭 있어야 합니다.
          </li>
          <li>
            이미 <code>.env.example</code>이 있으면 그걸 복사해 <code>.env</code>로 이름만 바꿔도 됩니다.
          </li>
          <li>
            아래 두 줄만 넣고, 등호 오른쪽을 본인 키로 바꿉니다. 따옴표·띄어쓰기 없이 한 줄에 붙여넣습니다.
          </li>
        </ol>
        <pre className="env-sample">{`GROQ_API_KEY=gsk_여기에_Groq키
GEMINI_API_KEY=여기에_Gemini키`}</pre>

        <p className="guide-h">2. Groq Whisper 키</p>
        <p>
          <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">
            console.groq.com/keys
          </a>
          에서 가입 → Create API Key. 키는 <code>gsk_</code>로 시작합니다. 이 키 하나로{" "}
          <code>whisper-large-v3</code> 전사를 합니다.
        </p>

        <p className="guide-h">3. Gemini 분석 키</p>
        <p>
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">
            aistudio.google.com/apikey
          </a>
          에서 Create API key. 분석은 전사본 텍스트만 보내며, 기본 모델은{" "}
          <code>gemini-3.5-flash</code>입니다.
        </p>

        <p className="guide-h">4. 저장 후 재시작</p>
        <p>
          <code>Ctrl+S</code>로 저장한 다음 <code>start.bat</code>을 끄고 다시 켜야 키가 적용됩니다. 이미
          떠 있는 서버는 예전 빈 키를 들고 있습니다.
        </p>

        <p className="guide-h">파일이 남는 위치</p>
        <p>
          브라우저를 닫아도 원본·변환 텍스트·요약 정리는 <code>data</code> 폴더와{" "}
          <code>data/nas-note.db</code>에 남습니다. 24MB가 넘는 파일은 시스템 임시 폴더에서 나눈 뒤{" "}
          <code>data</code>에만 결과 조각을 저장합니다. <code>data</code> 폴더를 지우면 그때 사라집니다.
        </p>

        <div className="modal-actions">
          <button className="btn btn-secondary" type="button" onClick={hideForever}>
            다시 보지 않기
          </button>
          <button className="btn btn-ghost" type="button" onClick={() => setOpen(false)}>
            지금만 닫기
          </button>
        </div>
        <p className="caption modal-hint">
          왼쪽은 이 브라우저에서 영구 숨김 · 오른쪽은 지금만 닫기(다시 켜면 표시)
        </p>
      </div>
    </div>
  );
}
