import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Loader } from "lucide-react";
import { api } from "../api";
import { AnalysisSections, NoteBody } from "../components/AnalysisSections";
import { formatAnalysisText, formatBytes, formatDuration, hydrateAnalysis, statusClass, statusLabel, unescapeGemini } from "../format";
import type { Project } from "../types";

export function ProjectPage() {
  const { id } = useParams();
  const projectId = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [missing, setMissing] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");
  const [toast, setToast] = useState("");
  const [confirm, setConfirm] = useState(false);
  const navigate = useNavigate();

  async function load() {
    try {
      const p = await api.project(projectId);
      setProject(p);
      setVideoUrl(p.video_url || "");
    } catch {
      setMissing(true);
    }
  }

  useEffect(() => {
    load();
  }, [projectId]);

  useEffect(() => {
    if (!project) return;
    if (project.status === "done" || project.status === "failed") return;
    const t = setInterval(async () => {
      try {
        const st = await api.status(projectId);
        if (st.status === "done" || st.status === "failed") {
          await load();
          return;
        }
        setProject((prev) =>
          prev
            ? {
                ...prev,
                status: st.status,
                percent: st.percent,
                error_message: st.error_message,
                chunks: st.chunks,
                transcript: st.transcript ?? prev.transcript,
                analysis_text: st.analysis_text ?? prev.analysis_text,
              }
            : prev
        );
      } catch {
        /* ignore poll errors */
      }
    }, 1000);
    return () => clearInterval(t);
  }, [project?.status, projectId]);

  if (missing) {
    return (
      <main className="content">
        <h1 className="display">이 프로젝트를 찾을 수 없습니다.</h1>
        <Link className="btn btn-primary" to="/">
          목록으로
        </Link>
      </main>
    );
  }

  if (!project) return null;

  const processing = ["pending", "splitting", "transcribing", "analyzing"].includes(project.status);
  const showPanes = processing || project.status === "done" || Boolean(project.transcript || project.analysis_text);

  async function retry() {
    try {
      await api.retry(projectId);
      await load();
    } catch (err) {
      setToast(err instanceof Error ? err.message : "재시도에 실패했습니다.");
      setTimeout(() => setToast(""), 3000);
    }
  }

  async function remove() {
    await api.remove(projectId);
    navigate("/");
  }

  async function saveVideo() {
    try {
      const raw = videoUrl.trim();
      const saved = await api.patch(projectId, { video_url: raw });
      setVideoUrl(saved.video_url);
      setProject((prev) => (prev ? { ...prev, video_url: saved.video_url } : prev));
      setToast(saved.video_url ? "파일 주소를 저장했습니다." : "파일 주소를 지웠습니다.");
      setTimeout(() => setToast(""), 3000);
    } catch (err) {
      setToast(err instanceof Error ? err.message : "주소 저장에 실패했습니다.");
      setTimeout(() => setToast(""), 3000);
    }
  }

  async function openSavedFile() {
    try {
      await saveVideo();
      await api.openFile(projectId);
    } catch (err) {
      setToast(err instanceof Error ? err.message : "파일을 열지 못했습니다.");
      setTimeout(() => setToast(""), 3000);
    }
  }

  async function copy(text: string) {
    await navigator.clipboard.writeText(text);
    setToast("복사했습니다.");
    setTimeout(() => setToast(""), 3000);
  }

  const hydrated = hydrateAnalysis(project.analysis, project.analysis_text);
  const analysisBody = unescapeGemini(project.analysis_text || "") || formatAnalysisText(hydrated);
  const transcriptBody = project.transcript || "";
  const showStructured =
    project.status === "done" &&
    Boolean(
      hydrated.detailed_summary ||
        hydrated.overall_summary ||
        hydrated.key_points.length ||
        hydrated.decisions.length ||
        hydrated.todos.length ||
        hydrated.important.length ||
        hydrated.extracted_info.length,
    );

  const sub =
    project.status === "pending"
      ? "대기열에 있습니다. 앞선 작업이 끝나면 시작합니다."
      : project.status === "splitting"
        ? "파일을 24MB 기준으로 나누고 있습니다."
        : project.status === "transcribing"
          ? "Groq Whisper로 텍스트를 옮기고 있습니다. 변환된 글이 왼쪽에 바로 쌓입니다."
          : project.status === "analyzing"
            ? "Gemini가 요약 정리를 작성하는 중입니다. 오른쪽에서 실시간으로 보입니다."
            : project.error_message || "";

  return (
    <main className="content wide">
      <div className="head-row">
        <div>
          <h1 className="display">{project.title}</h1>
          {processing ? (
            <p className="sub" aria-live="polite">
              {sub}
            </p>
          ) : (
            <p className="caption">
              {project.date.replaceAll("-", ".")}
              {project.duration ? `  ·  ${formatDuration(project.duration)}` : ""}
              {`  ·  ${project.original_filename}`}
            </p>
          )}
        </div>
        <div>
          <span className={`badge ${statusClass(project.status)}`}>{statusLabel(project.status)}</span>
        </div>
      </div>

      {processing ? (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${project.percent}%` }} />
            </div>
            <span className="mono caption">{project.percent}%</span>
          </div>
          {project.chunks.length ? <PartList project={project} /> : null}
          <p className="hint">이 창을 닫아도 처리는 계속됩니다. 변환 텍스트와 요약 정리가 아래 두 칸에 같이 표시됩니다.</p>
        </>
      ) : null}

      {project.status === "failed" ? (
        <>
          <div className="banner">{project.error_message}</div>
          {project.chunks.length ? <PartList project={project} /> : null}
          <button className="btn btn-primary" type="button" onClick={retry}>
            이어서 재시도
          </button>
        </>
      ) : null}

      {showPanes ? (
        <div className="result-grid">
          <section className="result-pane">
            <div className="pane-head">
              <p className="overline">변환 텍스트</p>
              {transcriptBody ? (
                <button className="btn btn-ghost" type="button" onClick={() => copy(transcriptBody)}>
                  복사
                </button>
              ) : null}
            </div>
            <p className={`transcript${processing && project.status === "transcribing" ? " live-caret" : ""}`}>
              {transcriptBody ||
                (processing
                  ? project.status === "transcribing"
                    ? " Groq가 말을 글로 옮기는 중입니다."
                    : "전사가 시작되면 여기에 글이 쌓입니다."
                  : "저장된 변환 텍스트가 없습니다.")}
            </p>
            <div className="video-link">
              <label htmlFor="video-url">파일 주소</label>
              <div className="video-row">
                <input
                  id="video-url"
                  value={videoUrl}
                  onChange={(e) => setVideoUrl(e.target.value)}
                  onBlur={() => {
                    const current = videoUrl.trim();
                    const saved = (project.video_url || "").trim();
                    if (current !== saved) void saveVideo();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void saveVideo();
                    }
                  }}
                  placeholder="D:\강의\1강.mp4 또는 \\nas\share\영상.mp4"
                />
                <button className="btn btn-secondary" type="button" onClick={() => void saveVideo()}>
                  저장
                </button>
                {videoUrl.trim() ? (
                  <button className="btn btn-secondary" type="button" onClick={() => void openSavedFile()}>
                    열기
                  </button>
                ) : null}
              </div>
              {videoUrl.trim() ? <p className="video-open">{videoUrl.trim()}</p> : null}
            </div>
          </section>
          <section className="result-pane main">
            <div className="pane-head">
              <p className="overline">요약 정리</p>
              {analysisBody ? (
                <button className="btn btn-ghost" type="button" onClick={() => copy(analysisBody)}>
                  복사
                </button>
              ) : null}
            </div>
            {showStructured ? (
              <AnalysisSections analysis={hydrated} />
            ) : (
              <div className={processing && project.status === "analyzing" ? "live-caret" : undefined}>
                {analysisBody ? (
                  <NoteBody text={analysisBody} />
                ) : (
                  <p className="transcript">
                    {processing
                      ? project.status === "analyzing"
                        ? "Gemini가 요약 정리를 쓰기 시작했습니다."
                        : "전사가 끝나면 여기에 요약 정리가 작성됩니다."
                      : "저장된 요약 정리가 없습니다."}
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      ) : null}

      {!processing ? (
        <p className="hint">
          <button className="btn btn-ghost" type="button" onClick={() => setConfirm(true)}>
            프로젝트 삭제
          </button>
        </p>
      ) : null}

      {toast ? <div className="toast">{toast}</div> : null}
      {confirm ? (
        <div className="modal-back">
          <div className="modal">
            <h2>이 프로젝트를 삭제할까요?</h2>
            <p>원본 파일, 텍스트, 분석이 디스크에서 삭제됩니다.</p>
            <button className="btn btn-secondary" type="button" onClick={() => setConfirm(false)}>
              취소
            </button>{" "}
            <button className="btn btn-danger" type="button" onClick={remove}>
              삭제
            </button>
          </div>
        </div>
      ) : null}
    </main>
  );
}

function PartList({ project }: { project: Project }) {
  return (
    <div className="card" style={{ marginBottom: 16 }}>
      {project.chunks.map((c) => (
        <div key={c.chunk_index} className={`part${c.status === "processing" ? " active" : ""}`}>
          <span
            className={`dot${c.status === "processing" ? " pulse" : ""}`}
            style={{
              background:
                c.status === "done"
                  ? "var(--success)"
                  : c.status === "failed"
                    ? "var(--danger)"
                    : c.status === "processing"
                      ? "var(--accent)"
                      : "var(--line-strong)",
            }}
          />
          <div style={{ flex: 1 }}>
            <strong>Part {String(c.chunk_index).padStart(2, "0")}</strong>
            {c.file_size ? <div className="caption">{formatBytes(c.file_size)}</div> : null}
          </div>
          <span className="caption">
            {c.status === "processing" ? (
              <>
                <Loader size={14} className="spin" /> 처리 중
              </>
            ) : c.status === "done" ? (
              "완료"
            ) : c.status === "failed" ? (
              "실패"
            ) : (
              "대기"
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
