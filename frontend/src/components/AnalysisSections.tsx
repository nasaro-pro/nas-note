import type { ReactNode } from "react";
import { unescapeGemini } from "../format";
import type { Analysis } from "../types";

const EMPTY = "이 녹음에서 확인된 항목이 없습니다.";

function renderInline(line: string): ReactNode {
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function headingText(line: string): string | null {
  const trimmed = line.trim();
  const hash = trimmed.match(/^#{1,3}\s*(.+)$/);
  if (hash && hash[1].trim() && !/^#+$/.test(hash[1].trim())) return hash[1].trim();
  const boxed = trimmed.match(/^【(.+)】$/);
  if (boxed) return boxed[1].trim();
  const bold = trimmed.match(/^\*\*([^*]+)\*\*$/);
  if (bold) return bold[1].trim();
  return null;
}

function isListLine(line: string): boolean {
  const t = line.trim();
  return !t || /^[-•*]\s+/.test(t) || /^\d+[.)]\s+/.test(t);
}

function listText(line: string): string {
  return line.trim().replace(/^[-•*]\s+/, "").replace(/^\d+[.)]\s+/, "");
}

export function NoteBody({ text, className }: { text: string; className?: string }) {
  const raw = normalizeNote(text);
  if (!raw) return <p className="muted">{EMPTY}</p>;

  const blocks = raw.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  return (
    <div className={className ?? "note-body"}>
      {blocks.map((block, i) => {
        const lines = block.split("\n").map((line) => line.trimEnd());
        const title = headingText(lines[0] || "");
        if (title) {
          const rest = lines.slice(1).map((line) => line.trim()).filter(Boolean);
          return (
            <div key={i} className="note-block">
              <h3>{title}</h3>
              {rest.length ? renderRest(rest) : null}
            </div>
          );
        }
        const filled = lines.map((line) => line.trim()).filter(Boolean);
        if (filled.length && filled.every(isListLine)) {
          return (
            <ul key={i}>
              {filled.map((line, j) => (
                <li key={j}>{renderInline(listText(line))}</li>
              ))}
            </ul>
          );
        }
        if (filled.length > 1) {
          return (
            <div key={i} className="note-block">
              {filled.map((line, j) => (
                <p key={j}>{renderInline(line)}</p>
              ))}
            </div>
          );
        }
        return (
          <p key={i}>
            {renderInline((filled[0] || "").trim())}
          </p>
        );
      })}
    </div>
  );
}

function normalizeNote(text: string): string {
  let cur = unescapeGemini(text).replace(/\r\n/g, "\n").replace(/\u00a0/g, " ");
  cur = cur.replace(/[ \t]+$/gm, "");
  cur = cur.replace(/[ \t]*#{1,3}[ \t]*/g, "\n\n## ");
  cur = cur.replace(/\n##\s*\n/g, "\n\n");
  cur = cur.replace(/\n{3,}/g, "\n\n");
  return cur.trim();
}

function renderRest(rest: string[]) {
  if (rest.every(isListLine)) {
    return (
      <ul>
        {rest.map((line, j) => (
          <li key={j}>{renderInline(listText(line))}</li>
        ))}
      </ul>
    );
  }
  return rest.map((line, j) => <p key={j}>{renderInline(line)}</p>);
}

function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="section">
      <p className="overline">{label}</p>
      {children}
    </div>
  );
}

function List({ items }: { items: string[] }) {
  if (!items.length) return <p className="muted">{EMPTY}</p>;
  return (
    <ul>
      {items.map((item, i) => {
        const text = unescapeGemini(item).trim();
        const complex = /\n/.test(text) || /^#{1,3}\s/.test(text);
        return <li key={i}>{complex ? <NoteBody text={text} className="note-item" /> : renderInline(text)}</li>;
      })}
    </ul>
  );
}

export function AnalysisSections({ analysis }: { analysis: Analysis }) {
  return (
    <div>
      <Block label="요약 정리">
        <NoteBody text={analysis.detailed_summary || ""} />
      </Block>
      <Block label="총정리">
        <NoteBody text={analysis.overall_summary || ""} />
      </Block>
      <Block label="정보 추가">
        <List items={analysis.extracted_info ?? []} />
      </Block>
      <Block label="용어정리">
        <List items={analysis.glossary ?? []} />
      </Block>
      <Block label="핵심 내용">
        <List items={analysis.key_points} />
      </Block>
      <Block label="결정 사항">
        <List items={analysis.decisions} />
      </Block>
      <Block label="할 일">
        <List items={analysis.todos} />
      </Block>
      <Block label="중요 내용">
        <List items={analysis.important} />
      </Block>
    </div>
  );
}
