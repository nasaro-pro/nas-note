import { DragEvent, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Mic, Upload } from "lucide-react";
import { Recorder } from "../components/Recorder";
import { api } from "../api";
import { formatBytes } from "../format";

const ACCEPT = ".mp3,.wav,.m4a,.mp4,.webm,.ogg,.weba,.flac,.mov,.mkv,.aac,.mpeg,.mpg,.3gp";
const FILE_EXT = ACCEPT.split(",");

type Mode = "choose" | "record" | "file";

export function UploadPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>(() => {
    const m = params.get("mode");
    if (m === "record") return "record";
    if (m === "choose") return "choose";
    return "file";
  });
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const m = params.get("mode");
    if (m === "record") setMode("record");
    else if (m === "choose") setMode("choose");
    else setMode("file");
  }, [params]);

  function goMode(next: Mode) {
    if (next === "choose") {
      setFile(null);
      setTitle("");
    }
    setMode(next);
    navigate(next === "file" ? "/upload" : `/upload?mode=${next}`, { replace: true });
  }

  function pick(next: File | null) {
    if (!next) return;
    const dot = next.name.lastIndexOf(".");
    const ext = dot >= 0 ? next.name.slice(dot).toLowerCase() : "";
    const typed = next.type.startsWith("audio/") || next.type.startsWith("video/");
    if (ext && !FILE_EXT.includes(ext) && !typed) {
      setError("MP3, WAV, M4A, MP4, MOV, WEBM, OGG만 올릴 수 있습니다.");
      return;
    }
    if (!ext && !typed) {
      setError("MP3, WAV, M4A, MP4, MOV, WEBM, OGG만 올릴 수 있습니다.");
      return;
    }
    setError("");
    setFile(next);
    setTitle(next.name.replace(/\.[^.]+$/, "") || "새 분석");
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
      <h1 className="display">{mode === "record" ? "녹음하고 정리" : "새 분석"}</h1>
      <p className="sub">
        {mode === "record"
          ? "녹음이 끝나면 전사와 요약 정리까지 자동으로 진행됩니다."
          : "MP3, WAV, M4A, MP4, MOV. 업로드 이후 개입 없이 끝까지 진행됩니다."}
      </p>
      {error ? <p className="err" role="alert">{error}</p> : null}

      {mode === "choose" ? (
        <div className="choice-grid">
          <button className="choice-card" type="button" onClick={() => goMode("record")}>
            <Mic className="icon" />
            <strong>지금 녹음</strong>
            <span className="caption">마이크를 켜고, 끝나면 바로 정리합니다.</span>
          </button>
          <button className="choice-card" type="button" onClick={() => goMode("file")}>
            <Upload className="icon" />
            <strong>파일 올리기</strong>
            <span className="caption">MP3, WAV, M4A, MP4, WEBM</span>
          </button>
        </div>
      ) : null}

      {mode === "record" ? (
        <>
          <Recorder
            onReady={(next, suggested) => {
              setFile(next);
              setTitle((prev) => prev || suggested);
            }}
            onClear={() => {
              setFile(null);
              setTitle("");
            }}
          />
          {file ? (
            <>
              <div className="field">
                <label htmlFor="title">제목</label>
                <input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className="rec-actions" style={{ marginTop: 16 }}>
                <button className="btn btn-ghost" type="button" onClick={() => goMode("choose")}>
                  다른 방법
                </button>
                <button className="btn btn-primary" type="button" disabled={busy} onClick={() => void submit()}>
                  {busy ? "올리는 중" : "정리 시작"}
                </button>
              </div>
            </>
          ) : (
            <div style={{ marginTop: 16 }}>
              <button className="btn btn-ghost" type="button" onClick={() => goMode("choose")}>
                다른 방법
              </button>
            </div>
          )}
        </>
      ) : null}

      {mode === "file" ? (
        <>
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
            <label htmlFor="file-title">프로젝트 제목</label>
            <input id="file-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="rec-actions" style={{ marginTop: 24 }}>
            <button
              className="btn btn-ghost"
              type="button"
              onClick={() => {
                setFile(null);
                setTitle("");
                goMode("choose");
              }}
            >
              다른 방법
            </button>
            <button className="btn btn-primary" type="button" disabled={!file || busy} onClick={() => void submit()}>
              {busy ? "처리 중" : "정리 시작"}
            </button>
          </div>
        </>
      ) : null}
    </main>
  );
}
