import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { highlight, statusClass, statusLabel } from "../format";
import type { SearchHit } from "../types";

const SOURCE: Record<SearchHit["source"], string> = {
  title: "제목",
  transcript: "원문",
  analysis: "분석",
};

export function SearchPage() {
  const [params] = useSearchParams();
  const q = params.get("q") || "";
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!q) {
      setHits([]);
      return;
    }
    api
      .search(q)
      .then((r) => setHits(r.results))
      .catch(() => setHits([]));
  }, [q]);

  return (
    <main className="content">
        <h1 className="display">‘{q}’ 검색 결과</h1>
        <p className="sub">{hits ? `${hits.length}건` : ""}</p>
        {hits && hits.length === 0 ? (
          <p>
            일치하는 내용이 없습니다.
            <br />
            검색어를 짧게 바꿔 보세요.
          </p>
        ) : null}
        {hits && hits.length > 0 ? (
          <div className="card">
            {hits.map((h, i) => (
              <button
                key={`${h.project_id}-${h.source}-${i}`}
                className="row"
                type="button"
                onClick={() =>
                  navigate(
                    h.source === "analysis"
                      ? `/projects/${h.project_id}?tab=analysis`
                      : `/projects/${h.project_id}`
                  )
                }
              >
                <div>
                  <h3>{h.title}</h3>
                  <div className="meta">
                    {SOURCE[h.source]}
                    {"  ·  "}
                    {highlight(h.snippet, q).map((part, idx) =>
                      typeof part === "string" ? (
                        <span key={idx}>{part}</span>
                      ) : (
                        <span key={idx} className="hit">
                          {part.hit}
                        </span>
                      )
                    )}
                  </div>
                </div>
                <span className={`badge ${statusClass(h.status)}`}>{statusLabel(h.status)}</span>
              </button>
            ))}
          </div>
        ) : null}
      </main>
  );
}
