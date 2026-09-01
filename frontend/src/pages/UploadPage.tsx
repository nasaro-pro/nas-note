import { DragEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload } from "lucide-react";
import { api } from "../api";
import { formatBytes } from "../format";

const ACCEPT = ".mp3,.wav,.m4a,.mp4";

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  function pick(next: File | null) {
    if (!next) return;
    const ext = next.name.slice(next.name.lastIndexOf(".")).toLowerCase();
    if (![".mp3", ".wav", ".m4a", ".mp4"].includes(ext)) {
      setError("MP3, WAV, M4A, MP4만 올릴 수 있습니다.");
      return;
    }
    setError("");
    setFile(next);
    setTitle(next.name.replace(/\.[^.]+$/, ""));
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    pick(e.dataTransfer.files[0] ?? null);
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const created = await api.upload(file, title.trim() || file.name);
      navigate(`/projects/${created.id}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "업로드에 실패했습니다.");
      setBusy(false);
    }
  }

  return (
    <main className="content">
        <h1 className="display">새 분석</h1>
        <p className="sub">MP3, WAV, M4A, MP4. 업로드 이후 개입 없이 끝까지 진행합니다.</p>
        {error ? <p className="err">{error}</p> : null}
        {!file ? (
          <button
            type="button"
            className={`drop${over ? " over" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setOver(true);
            }}
            onDragLeave={() => setOver(false)}
            onDrop={onDrop}
          >
            <Upload className="icon" />
            <div>파일을 여기에 놓거나 클릭해서 선택</div>
            <div className="caption">최대 용량 제한 없음. 24MB 넘으면 자동 분할.</div>
          </button>
        ) : (
          <div className="card file-card">
            <div>
              <strong>{file.name}</strong>
              <div className="caption">{formatBytes(file.size)}</div>
            </div>
            <button className="btn btn-ghost" type="button" onClick={() => setFile(null)}>
              다른 파일
            </button>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          hidden
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
        <div className="field">
          <label htmlFor="title">프로젝트 제목</label>
          <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div style={{ marginTop: 24 }}>
          <button className="btn btn-primary" type="button" disabled={!file || busy} onClick={submit}>
            {busy ? "처리 중" : "분석 시작"}
          </button>
        </div>
      </main>
  );
}
