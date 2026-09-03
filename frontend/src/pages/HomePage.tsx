import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FileAudio } from "lucide-react";
import { api } from "../api";
import { formatBytes, formatDateLabel, formatDuration, statusClass, statusLabel } from "../format";
import type { Health, Project } from "../types";

export function HomePage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [down, setDown] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let stop = false;

    async function load() {
      try {
        const [h, p] = await Promise.all([api.health(), api.projects()]);
        if (stop) return;
        setHealth(h);
        setProjects(p);
        setDown(false);
      } catch {
        if (!stop) {
          setDown(true);
          setProjects((prev) => prev ?? []);
        }
      }
    }

    load();
    const onFocus = () => {
      void load();
    };
    const onVis = () => {
      if (document.visibilityState === "visible") void load();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVis);
    const timer = window.setInterval(() => {
      void load();
    }, 4000);

    return () => {
      stop = true;
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVis);
      window.clearInterval(timer);
    };
  }, []);

  const groups = groupByDate(projects ?? []);

  return (
    <main className="content">
        <div className="head-row">
          <div>
            <h1 className="display">nas-note</h1>
            <p className="sub">이 컴퓨터에만 남는 개인 정리 노트. 긴 녹음은 텍스트와 요약까지 자동으로 끝납니다.</p>
          </div>
          {projects && projects.length > 0 ? (
            <div className="rec-actions">
              <p className="caption">{projects.length}개 프로젝트</p>
              <Link className="btn btn-secondary" to="/upload?mode=record">
                녹음
              </Link>
              <Link className="btn btn-primary" to="/upload">
                새 분석
              </Link>
            </div>
          ) : null}
        </div>
        {down ? (
          <div className="banner">백엔드에 연결할 수 없습니다. uvicorn이 켜져 있는지 확인하세요.</div>
        ) : null}
        {health && !health.ffmpeg ? (
          <div className="banner warn">
            이 컴퓨터에 FFmpeg가 없습니다. start.bat을 다시 실행하면 자동 설치를 시도합니다.
          </div>
        ) : null}
        {health && !health.groq_key ? (
          <div className="banner">Groq Whisper 키가 없습니다. .env의 GROQ_API_KEY를 확인하세요.</div>
        ) : null}
        {health && !health.gemini_key ? (
          <div className="banner">Gemini 키가 없습니다. 전사는 되지만 분석은 실패합니다.</div>
        ) : null}

        {projects && projects.length === 0 ? (
          <div className="empty">
            <FileAudio className="icon" />
            <h2>아직 분석한 녹음이 없습니다</h2>
            <p>3~4시간 파일이어도 업로드하면 분할, 전사, 요약까지 자동으로 진행됩니다.</p>
            <div className="rec-actions" style={{ justifyContent: "center" }}>
              <Link className="btn btn-primary" to="/upload?mode=file">
                첫 녹음 올리기
              </Link>
              <Link className="btn btn-secondary" to="/upload?mode=record">
                녹음하기
              </Link>
            </div>
          </div>
        ) : null}

        {groups.map((g) => (
          <div key={g.date}>
            <p className="date-label">{formatDateLabel(g.date)}</p>
            <div className="card">
              {g.items.map((p) => (
                <button
                  key={p.id}
                  className="row"
                  type="button"
                  onClick={() => navigate(`/projects/${p.id}`)}
                >
                  <div>
                    <h3>{p.title}</h3>
                    <div className="meta">
                      {p.original_filename}
                      {p.file_size ? `  ·  ${formatBytes(p.file_size)}` : ""}
                    </div>
                  </div>
                  <div className="right">
                    <div className="mono caption">
                      {p.status === "transcribing" || p.status === "splitting"
                        ? `Part ${p.chunks.filter((c) => c.status === "done").length}/${p.chunks.length || "?"}`
                        : formatDuration(p.duration)}
                    </div>
                    <span className={`badge ${statusClass(p.status)}`}>{statusLabel(p.status)}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </main>
  );
}

function groupByDate(items: Project[]): { date: string; items: Project[] }[] {
  const map = new Map<string, Project[]>();
  for (const p of items) {
    const list = map.get(p.date) ?? [];
    list.push(p);
    map.set(p.date, list);
  }
  return [...map.entries()].map(([date, grouped]) => ({ date, items: grouped }));
}
