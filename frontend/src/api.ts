import type { Health, Note, Project, SearchHit } from "./types";

const BASES = ["", "http://127.0.0.1:8000", "http://localhost:8000"];
let workingBase: string | null = null;

function errorMessage(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    if (typeof first === "string" && first.trim()) return first;
    if (first && typeof first === "object" && "msg" in first) {
      const msg = (first as { msg?: unknown }).msg;
      if (typeof msg === "string" && msg.trim()) return msg;
    }
  }
  if (status === 502 || status === 503 || status === 504) {
    return "백엔드에 연결하지 못했습니다. start.bat을 다시 실행하세요.";
  }
  return `요청 실패 (${status})`;
}

function connectError(err: unknown): Error {
  const msg = err instanceof Error ? err.message : String(err);
  if (/failed to fetch|networkerror|load failed|econnrefused|network error/i.test(msg)) {
    return new Error("백엔드에 연결하지 못했습니다. start.bat을 다시 실행한 뒤 http://localhost:5173/ 으로 여세요.");
  }
  return err instanceof Error ? err : new Error(msg);
}

function orderedBases(): string[] {
  if (workingBase === null) return BASES;
  return [workingBase, ...BASES.filter((b) => b !== workingBase)];
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  let last: unknown;
  for (const base of orderedBases()) {
    try {
      const res = await fetch(`${base}${url}`, init);
      if (res.status === 204) {
        workingBase = base;
        return undefined as T;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        if (res.status === 502 || res.status === 503 || res.status === 504) {
          last = new Error(errorMessage(data, res.status));
          continue;
        }
        throw new Error(errorMessage(data, res.status));
      }
      workingBase = base;
      return data as T;
    } catch (err) {
      if (err instanceof Error && !/백엔드에 연결|failed to fetch|networkerror|load failed/i.test(err.message) && !/요청 실패 \(50[234]\)/.test(err.message)) {
        throw err;
      }
      last = err;
    }
  }
  throw connectError(last);
}

export const api = {
  health: () => req<Health>("/api/health"),
  projects: () => req<Project[]>("/api/projects"),
  project: (id: number) => req<Project>(`/api/projects/${id}`),
  status: (id: number) =>
    req<
      Pick<Project, "id" | "status" | "percent" | "error_message" | "chunks" | "transcript" | "analysis_text">
    >(`/api/projects/${id}/status`),
  retry: (id: number) => req<{ id: number }>(`/api/projects/${id}/retry`, { method: "POST" }),
  patch: (id: number, body: { video_url: string }) =>
    req<{ id: number; video_url: string }>(`/api/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  openFile: (id: number) => req<{ ok: boolean }>(`/api/projects/${id}/open-file`, { method: "POST" }),
  remove: (id: number) => req<void>(`/api/projects/${id}`, { method: "DELETE" }),
  search: (q: string) => req<{ query: string; results: SearchHit[] }>(`/api/search?q=${encodeURIComponent(q)}`),
  upload: async (file: File, title: string) => {
    const body = new FormData();
    body.append("file", file);
    body.append("title", title);
    return req<{ id: number; status: string }>("/api/projects", { method: "POST", body });
  },
  recordStart: () => req<{ ok: boolean }>("/api/record/start", { method: "POST" }),
  recordStop: async () => {
    let last: unknown;
    for (const base of orderedBases()) {
      try {
        const res = await fetch(`${base}/api/record/stop`, { method: "POST" });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          if (res.status === 502 || res.status === 503 || res.status === 504) {
            last = new Error(errorMessage(data, res.status));
            continue;
          }
          throw new Error(errorMessage(data, res.status));
        }
        workingBase = base;
        return res.blob();
      } catch (err) {
        if (err instanceof Error && !/백엔드에 연결|failed to fetch|networkerror|load failed/i.test(err.message)) {
          throw err;
        }
        last = err;
      }
    }
    throw connectError(last);
  },
  notes: () => req<Note[]>("/api/notes"),
  createNote: () => req<Note>("/api/notes", { method: "POST" }),
  saveNote: (id: string, body: { title?: string; body?: string }) =>
    req<Note>(`/api/notes/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  removeNote: (id: string) => req<void>(`/api/notes/${id}`, { method: "DELETE" }),
};
