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

export function formatAnalysisText(analysis: {
  overall_summary: string;
  extracted_info?: string[];
  key_points: string[];
  detailed_summary: string;
  decisions: string[];
  todos: string[];
  important: string[];
} | null | undefined): string {
  if (!analysis) return "";
  const bullets = (items: string[]) => (items.length ? items.map((x) => `- ${x}`).join("\n") : "없음");
  return [
    "【총정리】",
    analysis.overall_summary.trim() || "없음",
    "",
    "【정보 추가】",
    bullets(analysis.extracted_info ?? []),
    "",
    "【요약 정리】",
    analysis.detailed_summary.trim() || "없음",
    "",
    "【핵심 내용】",
    bullets(analysis.key_points),
    "",
    "【결정 사항】",
    bullets(analysis.decisions),
    "",
    "【할 일】",
    bullets(analysis.todos),
    "",
    "【중요 내용】",
    bullets(analysis.important),
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
