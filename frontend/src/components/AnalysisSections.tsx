import type { ReactNode } from "react";
import type { Analysis } from "../types";

const EMPTY = "이 녹음에서 확인된 항목이 없습니다.";

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
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

export function AnalysisSections({ analysis }: { analysis: Analysis }) {
  return (
    <div>
      <Block label="요약 정리">
        <p className="study-notes">{analysis.detailed_summary || EMPTY}</p>
      </Block>
      <Block label="총정리">
        <p>{analysis.overall_summary || EMPTY}</p>
      </Block>
      <Block label="정보 추가">
        <List items={analysis.extracted_info ?? []} />
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
