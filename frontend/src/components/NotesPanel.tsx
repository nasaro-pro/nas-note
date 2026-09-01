import { useEffect, useRef, useState } from "react";
import { PenLine, Plus, Trash2 } from "lucide-react";
import { api } from "../api";
import { formatDateLabel, formatDateTime, formatTime } from "../format";
import type { Note } from "../types";

function groupNotes(notes: Note[]): { date: string; items: Note[] }[] {
  const map = new Map<string, Note[]>();
  for (const note of notes) {
    const list = map.get(note.date) ?? [];
    list.push(note);
    map.set(note.date, list);
  }
  return [...map.entries()].map(([date, items]) => ({ date, items }));
}

export function NotesPanel() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [saved, setSaved] = useState(true);
  const timer = useRef<number | null>(null);
  const dirty = useRef(false);

  const active = notes.find((n) => n.id === activeId) || null;

  async function refresh(selectId?: string) {
    const list = await api.notes();
    setNotes(list);
    const next = selectId || activeId || list[0]?.id || null;
    setActiveId(next);
    const found = list.find((n) => n.id === next);
    dirty.current = false;
    if (found) {
      setTitle(found.title);
      setBody(found.body);
      setSaved(true);
    } else {
      setTitle("");
      setBody("");
    }
  }

  useEffect(() => {
    refresh().catch(() => setNotes([]));
  }, []);

  useEffect(() => {
    if (!activeId || !dirty.current) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        const updated = await api.saveNote(activeId, { title, body });
        setNotes((list) => list.map((n) => (n.id === updated.id ? { ...n, ...updated } : n)));
        setSaved(true);
      } catch {
        /* keep unsaved */
      }
    }, 450);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [title, body, activeId]);

  async function create() {
    const note = await api.createNote();
    await refresh(note.id);
  }

  async function remove() {
    if (!activeId) return;
    await api.removeNote(activeId);
    const rest = notes.filter((n) => n.id !== activeId);
    await refresh(rest[0]?.id);
  }

  function preview(note: Note) {
    return note.title.trim() || note.body.trim().slice(0, 28) || "제목 없음";
  }

  const groups = groupNotes(notes);

  return (
    <aside className="notes-panel">
      <div className="notes-head">
        <div className="notes-head-copy">
          <p className="overline">노트</p>
          <p className="notes-hint">이 컴퓨터 notes 폴더에만 저장</p>
        </div>
        <button className="btn btn-ghost" type="button" onClick={() => void create()}>
          <Plus size={16} />
          새 메모
        </button>
      </div>
      {notes.length === 0 ? (
        <div className="notes-empty">
          <PenLine size={22} />
          <p>적어 두고 싶은 것을 남겨 두세요.</p>
          <button className="btn btn-secondary" type="button" onClick={() => void create()}>
            첫 메모 쓰기
          </button>
        </div>
      ) : (
        <div className="notes-split">
          <ul className="notes-list">
            {groups.map((g) => (
              <li key={g.date} className="notes-group">
                <p className="notes-date">{formatDateLabel(g.date)}</p>
                {g.items.map((note) => (
                  <button
                    key={note.id}
                    type="button"
                    className={`notes-item${note.id === activeId ? " on" : ""}`}
                    onClick={() => {
                      dirty.current = false;
                      setActiveId(note.id);
                      setTitle(note.title);
                      setBody(note.body);
                      setSaved(true);
                    }}
                  >
                    <span className="notes-item-title">{preview(note)}</span>
                    <span className="notes-item-time">{formatTime(note.updated_at)}</span>
                  </button>
                ))}
              </li>
            ))}
          </ul>
          <div className="notes-editor">
            <input
              className="notes-title"
              value={title}
              placeholder="제목"
              onChange={(e) => {
                dirty.current = true;
                setTitle(e.target.value);
                setSaved(false);
              }}
            />
            <textarea
              className="notes-body"
              value={body}
              placeholder="생각을 적습니다."
              onChange={(e) => {
                dirty.current = true;
                setBody(e.target.value);
                setSaved(false);
              }}
            />
            <div className="notes-foot">
              <span className="caption notes-stamp">
                {active
                  ? `${formatDateTime(active.created_at || `${active.date}T00:00:00`)} 작성 · ${saved ? "저장됨" : "저장 중"}`
                  : saved
                    ? "저장됨"
                    : "저장 중"}
              </span>
              {active ? (
                <button className="btn btn-ghost" type="button" onClick={() => void remove()}>
                  <Trash2 size={14} />
                  삭제
                </button>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
