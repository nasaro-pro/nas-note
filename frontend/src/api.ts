import type { Health, Note, Project, SearchHit } from "./types";

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
  return `요청 실패 (${status})`;
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(errorMessage(data, res.status));
  }
  return data as T;
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
    const res = await fetch("/api/record/stop", { method: "POST" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(errorMessage(data, res.status));
    }
    return res.blob();
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
