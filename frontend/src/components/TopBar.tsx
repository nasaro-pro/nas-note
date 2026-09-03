import { FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { FolderClosed, Mic, PenLine, Search } from "lucide-react";
import { useLayout } from "../layout";

export function TopBar() {
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const navigate = useNavigate();
  const location = useLocation();
  const { notesOpen, railOpen, toggleNotes, toggleRail } = useLayout();
  const path = location.pathname;
  const back = path === "/upload" || path.startsWith("/projects/");
  const showSearch = path !== "/upload";

  useEffect(() => {
    setQ(params.get("q") || "");
  }, [params]);

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const query = q.trim();
    if (query) navigate(`/search?q=${encodeURIComponent(query)}`);
  }

  return (
    <header className="topbar">
      <button
        className={`btn btn-ghost write-btn${notesOpen ? " on" : ""}`}
        type="button"
        onClick={toggleNotes}
      >
        <PenLine size={18} />
        글쓰기
      </button>
      {back ? (
        <Link className="btn btn-ghost" to="/">
          목록으로
        </Link>
      ) : null}
      <Link className="wordmark" to="/">
        nas-note
      </Link>
      <span className="spacer" />
      {showSearch ? (
        <form className="search-wrap" onSubmit={onSearch}>
          <Search size={18} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="프로젝트 · 텍스트 · 요약 검색"
          />
        </form>
      ) : null}
      <Link className="btn btn-secondary" to="/upload?mode=record">
        <Mic size={18} />
        녹음
      </Link>
      <Link className="btn btn-primary" to="/upload">
        새 분석
      </Link>
      <button
        className={`btn btn-ghost write-btn${railOpen ? " on" : ""}`}
        type="button"
        onClick={toggleRail}
      >
        <FolderClosed size={18} />
        파일
      </button>
    </header>
  );
}
