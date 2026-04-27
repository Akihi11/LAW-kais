import { Fragment, type ReactNode } from "react";

interface MarkdownRendererProps {
  content: string;
}

function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={`${keyPrefix}-${index}`}>{part.slice(2, -2)}</strong>;
    }
    return <Fragment key={`${keyPrefix}-${index}`}>{part}</Fragment>;
  });
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index]?.trimEnd() ?? "";
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const Tag = `h${Math.min(level, 6)}` as keyof JSX.IntrinsicElements;
      blocks.push(<Tag key={`heading-${index}`}>{renderInline(text, `heading-${index}`)}</Tag>);
      index += 1;
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (unorderedMatch) {
      const items: string[] = [];
      while (index < lines.length) {
        const candidate = lines[index]?.trim() ?? "";
        const match = candidate.match(/^[-*]\s+(.+)$/);
        if (!match) {
          break;
        }
        items.push(match[1]);
        index += 1;
      }

      blocks.push(
        <ul key={`ul-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`ul-${index}-${itemIndex}`}>{renderInline(item, `ul-${index}-${itemIndex}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (orderedMatch) {
      const items: string[] = [];
      while (index < lines.length) {
        const candidate = lines[index]?.trim() ?? "";
        const match = candidate.match(/^\d+\.\s+(.+)$/);
        if (!match) {
          break;
        }
        items.push(match[1]);
        index += 1;
      }

      blocks.push(
        <ol key={`ol-${index}`}>
          {items.map((item, itemIndex) => (
            <li key={`ol-${index}-${itemIndex}`}>{renderInline(item, `ol-${index}-${itemIndex}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length) {
      const candidate = lines[index]?.trimEnd() ?? "";
      const candidateTrimmed = candidate.trim();
      if (!candidateTrimmed) {
        index += 1;
        break;
      }
      if (/^(#{1,6})\s+/.test(candidateTrimmed) || /^[-*]\s+/.test(candidateTrimmed) || /^\d+\.\s+/.test(candidateTrimmed)) {
        break;
      }
      paragraphLines.push(candidateTrimmed);
      index += 1;
    }

    blocks.push(
      <p key={`p-${index}`}>
        {paragraphLines.map((paragraphLine, lineIndex) => (
          <Fragment key={`p-${index}-${lineIndex}`}>
            {lineIndex > 0 ? <br /> : null}
            {renderInline(paragraphLine, `p-${index}-${lineIndex}`)}
          </Fragment>
        ))}
      </p>,
    );
  }

  return <div className="report-markdown">{blocks}</div>;
}

