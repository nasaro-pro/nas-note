import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { formatDateLabel, statusClass, statusLabel } from "../format";
import type { Project } from "../types";

function groupByDate(items: Project[]): { date: string; items: Project[] }[] {
  const map = new Map<string, Project[]>();
  for (const p of items) {
    const list = map.get(p.date) ?? [];
    list.push(p);
    map.set(p.date, list);
  }
  return [...map.entries()].map(([date, grouped]) => ({ date, items: grouped }));
}

export function FileRail({ onClose }: { onClose: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadErr, setLoadErr] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  async function load() {
    try {
      setProjects(await api.projects());
      setLoadErr(false);
    } catch {
      setLoadErr(true);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [location.pathname]);

  const match = location.pathname.match(/^\/projects\/(\d+)/);
  const activeId = match ? Number(match[1]) : null;
  const groups = groupByDate(projects);

  return (
    <aside className="file-rail">
      <div className="rail-head">
        <p className="overline">파일</p>
        <button className="btn btn-ghost" type="button" onClick={onClose}>
          닫기
        </button>
      </div>
      <p className="caption muted rail-hint">프로젝트를 누르면 가운데에 내용이 열립니다.</p>
      {projects.length === 0 ? (
        <p className="caption muted">
          {loadErr ? "목록을 불러오지 못했습니다." : "아직 저장된 파일이 없습니다."}
        </p>
      ) : null}
      {groups.map((g) => (
        <div key={g.date} className="rail-date">
          <p className="date-label">{formatDateLabel(g.date)}</p>
          {g.items.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`rail-project${activeId === p.id ? " on" : ""}`}
              onClick={() => navigate(`/projects/${p.id}`)}
            >
              <span className="rail-title">{p.title}</span>
              <span className={`badge ${statusClass(p.status)}`}>{statusLabel(p.status)}</span>
            </button>
          ))}
        </div>
      ))}
    </aside>
  );
}
