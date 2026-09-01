import { createContext, ReactNode, useContext, useState } from "react";

const NOTES_KEY = "nas-note.notes.open";
const RAIL_KEY = "nas-note.fileRail.open";

type LayoutState = {
  notesOpen: boolean;
  railOpen: boolean;
  toggleNotes: () => void;
  toggleRail: () => void;
  closeRail: () => void;
};

const LayoutContext = createContext<LayoutState | null>(null);

function readFlag(key: string, fallback: boolean): boolean {
  try {
    const raw = localStorage.getItem(key);
    if (raw == null) return fallback;
    return raw !== "0";
  } catch {
    return fallback;
  }
}

function writeFlag(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function LayoutProvider({ children }: { children: ReactNode }) {
  const [notesOpen, setNotesOpen] = useState(() => readFlag(NOTES_KEY, false));
  const [railOpen, setRailOpen] = useState(() => readFlag(RAIL_KEY, true));

  function toggleNotes() {
    setNotesOpen((open) => {
      const next = !open;
      writeFlag(NOTES_KEY, next);
      return next;
    });
  }

  function toggleRail() {
    setRailOpen((open) => {
      const next = !open;
      writeFlag(RAIL_KEY, next);
      return next;
    });
  }

  function closeRail() {
    writeFlag(RAIL_KEY, false);
    setRailOpen(false);
  }

  return (
    <LayoutContext.Provider value={{ notesOpen, railOpen, toggleNotes, toggleRail, closeRail }}>
      {children}
    </LayoutContext.Provider>
  );
}

export function useLayout(): LayoutState {
  const ctx = useContext(LayoutContext);
  if (!ctx) throw new Error("useLayout");
  return ctx;
}
