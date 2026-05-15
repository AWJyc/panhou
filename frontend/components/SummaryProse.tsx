import { ReactNode } from "react";

interface Props {
  md: string;
  className?: string;
}

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const regex = /\*\*([^*]+)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(<strong key={key++}>{match[1]}</strong>);
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

export function SummaryProse({ md, className = "" }: Props) {
  if (!md.trim()) {
    return <p className={`text-ink-muted ${className}`}>本次报告暂无正文。</p>;
  }

  // 把转义的 \n 还原成真换行
  const normalized = md.replace(/\\n/g, "\n");

  const lines = normalized.split("\n");
  const blocks: ReactNode[] = [];
  let listBuffer: string[] = [];
  let key = 0;

  const flushList = () => {
    if (listBuffer.length) {
      blocks.push(
        <ul key={key++}>
          {listBuffer.map((item, i) => (
            <li key={i}>{renderInline(item)}</li>
          ))}
        </ul>
      );
      listBuffer = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.trim() === "") {
      flushList();
      continue;
    }
    if (/^#{1,2}\s/.test(line)) {
      flushList();
      const text = line.replace(/^#+\s*/, "");
      blocks.push(<h2 key={key++}>{renderInline(text)}</h2>);
      continue;
    }
    if (/^#{3}\s/.test(line)) {
      flushList();
      const text = line.replace(/^#+\s*/, "");
      blocks.push(<h3 key={key++}>{renderInline(text)}</h3>);
      continue;
    }
    if (/^[-*]\s|^\d+\.\s/.test(line)) {
      listBuffer.push(line.replace(/^[-*]\s|^\d+\.\s/, ""));
      continue;
    }
    flushList();
    blocks.push(<p key={key++}>{renderInline(line)}</p>);
  }
  flushList();

  return <div className={`prose-ai ${className}`}>{blocks}</div>;
}
