export function statusLabel(status: string): string {
  switch (status) {
    case "pending":
      return "대기열";
    case "splitting":
      return "분할 중";
    case "transcribing":
      return "전사 중";
    case "analyzing":
      return "분석 중";
    case "done":
      return "완료";
    case "failed":
      return "실패";
    default:
      return status;
  }
}

export function statusClass(status: string): string {
  if (status === "done") return "b-done";
  if (status === "failed") return "b-fail";
  if (status === "analyzing") return "b-ana";
  if (status === "pending") return "b-wait";
  return "b-run";
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h) return `${h}시간 ${m}분`;
  if (m) return `${m}분`;
  return `${s}초`;
}

export function formatBytes(n: number | null | undefined): string {
  if (!n) return "";
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDateLabel(iso: string): string {
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${Number(y)}년 ${Number(m)}월 ${Number(d)}일`;
}

function parseStamp(iso?: string): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatTime(iso?: string): string {
  const d = parseStamp(iso);
  if (!d) return "";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function formatDateTime(iso?: string): string {
  const d = parseStamp(iso);
  if (!d) return iso ? formatDateLabel(iso.slice(0, 10)) : "";
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 ${formatTime(iso)}`;
}

export function unescapeGemini(text: string | null | undefined): string {
  let cur = text ?? "";
  for (let i = 0; i < 4; i += 1) {
    const next = cur.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n").replace(/\\t/g, "\t");
    if (next === cur) break;
    cur = next;
  }
  return cur.replace(/\\"/g, '"');
}

export function asItems(value: string | string[] | null | undefined): string[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value.flatMap((item) => asItems(item)).filter((item) => item && item !== "없음");
  }
  const text = unescapeGemini(String(value)).trim();
  if (!text || text === "없음") return [];
  try {
    const parsed = JSON.parse(text) as unknown;
    if (Array.isArray(parsed)) return asItems(parsed as string[]);
    if (typeof parsed === "string") return asItems(parsed);
  } catch {
    /* plain text */
  }
  return text
    .split(/\n+/)
    .map((line) => line.replace(/^[-•*]\s+/, "").replace(/^\d+[.)]\s+/, "").trim())
    .filter((line) => line && line !== "없음");
}

const SECTION_KEYS: Record<string, "overall_summary" | "extracted_info" | "glossary" | "detailed_summary" | "key_points" | "decisions" | "todos" | "important"> = {
  총정리: "overall_summary",
  "정보 추가": "extracted_info",
  정보추가: "extracted_info",
  용어정리: "glossary",
  "용어 정리": "glossary",
  "요약 정리": "detailed_summary",
  요약정리: "detailed_summary",
  "핵심 내용": "key_points",
  핵심내용: "key_points",
  "결정 사항": "decisions",
  결정사항: "decisions",
  "할 일": "todos",
  할일: "todos",
  "중요 내용": "important",
  중요내용: "important",
};

export function parseAnalysisDump(text: string): {
  overall_summary: string;
  extracted_info: string[];
  glossary: string[];
  detailed_summary: string;
  key_points: string[];
  decisions: string[];
  todos: string[];
  important: string[];
} {
  const empty = {
    overall_summary: "",
    extracted_info: [] as string[],
    glossary: [] as string[],
    detailed_summary: "",
    key_points: [] as string[],
    decisions: [] as string[],
    todos: [] as string[],
    important: [] as string[],
  };
  const raw = unescapeGemini(text).replace(/\r\n/g, "\n");
  const parts = raw.split(/【([^】]+)】/);
  if (parts.length < 3) return empty;
  for (let i = 1; i + 1 < parts.length; i += 2) {
    const key = SECTION_KEYS[parts[i].trim()];
    const body = parts[i + 1].trim();
    if (!key) continue;
    if (key === "overall_summary" || key === "detailed_summary") {
      empty[key] = body === "없음" ? "" : body;
    } else {
      empty[key] = body === "없음" ? [] : asItems(body);
    }
  }
  return empty;
}

export function hydrateAnalysis(
  analysis: {
    overall_summary: string;
    extracted_info?: string[];
    glossary?: string[];
    key_points: string[];
    detailed_summary: string;
    decisions: string[];
    todos: string[];
    important: string[];
  } | null | undefined,
  dump?: string,
) {
  const parsed = dump ? parseAnalysisDump(dump) : null;
  const base = {
    overall_summary: unescapeGemini(analysis?.overall_summary || ""),
    extracted_info: asItems(analysis?.extracted_info),
    glossary: asItems(analysis?.glossary),
    key_points: asItems(analysis?.key_points),
    detailed_summary: unescapeGemini(analysis?.detailed_summary || ""),
    decisions: asItems(analysis?.decisions),
    todos: asItems(analysis?.todos),
    important: asItems(analysis?.important),
  };
  if (!parsed) return base;
  if (!base.overall_summary) base.overall_summary = parsed.overall_summary;
  if (!base.detailed_summary) base.detailed_summary = parsed.detailed_summary;
  if (!base.extracted_info.length) base.extracted_info = parsed.extracted_info;
  if (!base.glossary.length) base.glossary = parsed.glossary;
  if (!base.key_points.length) base.key_points = parsed.key_points;
  if (!base.decisions.length) base.decisions = parsed.decisions;
  if (!base.todos.length) base.todos = parsed.todos;
  if (!base.important.length) base.important = parsed.important;
  return base;
}

export function formatAnalysisText(analysis: {
  overall_summary: string;
  extracted_info?: string[];
  glossary?: string[];
  key_points: string[];
  detailed_summary: string;
  decisions: string[];
  todos: string[];
  important: string[];
} | null | undefined): string {
  const note = hydrateAnalysis(analysis);
  if (
    !note.overall_summary.trim() &&
    !note.detailed_summary.trim() &&
    !note.extracted_info.length &&
    !note.glossary.length &&
    !note.key_points.length &&
    !note.decisions.length &&
    !note.todos.length &&
    !note.important.length
  ) {
    return "";
  }
  const bullets = (items: string[]) => (items.length ? items.map((x) => `- ${x}`).join("\n") : "없음");
  return [
    "【총정리】",
    note.overall_summary.trim() || "없음",
    "",
    "【정보 추가】",
    bullets(note.extracted_info),
    "",
    "【용어정리】",
    bullets(note.glossary),
    "",
    "【요약 정리】",
    note.detailed_summary.trim() || "없음",
    "",
    "【핵심 내용】",
    bullets(note.key_points),
    "",
    "【결정 사항】",
    bullets(note.decisions),
    "",
    "【할 일】",
    bullets(note.todos),
    "",
    "【중요 내용】",
    bullets(note.important),
  ].join("\n");
}

export function highlight(text: string, q: string): Array<string | { hit: string }> {
  if (!q) return [text];
  const out: Array<string | { hit: string }> = [];
  const lower = text.toLowerCase();
  const needle = q.toLowerCase();
  let i = 0;
  while (i < text.length) {
    const at = lower.indexOf(needle, i);
    if (at < 0) {
      out.push(text.slice(i));
      break;
    }
    if (at > i) out.push(text.slice(i, at));
    out.push({ hit: text.slice(at, at + q.length) });
    i = at + q.length;
  }
  return out;
}
