import { Fragment, type ReactNode } from "react";

/**
 * Minimal, safe Markdown renderer for coach/assistant messages.
 *
 * The backend returns lightweight Markdown (headings, bold, inline code, ordered
 * and unordered lists, paragraphs). We render it to React elements — never to raw
 * HTML — so there is no injection surface (no `dangerouslySetInnerHTML`). This is a
 * deliberately small block/inline parser rather than a `react-markdown` dependency,
 * matching the frontend's lean-foundation philosophy (see `cn` in lib/utils).
 *
 * Supported block syntax:
 *   - `#`, `##`, `###` headings
 *   - `- ` / `* ` unordered list items
 *   - `1. ` ordered list items
 *   - blank-line-separated paragraphs (single newlines become <br/>)
 * Supported inline syntax: `**bold**` and `` `code` ``.
 * Anything unrecognised renders as plain text.
 */
export function Markdown({ text }: { text: string }) {
  return <div className="coach-md space-y-2.5 text-sm leading-relaxed">{renderBlocks(text)}</div>;
}

type Block =
  | { kind: "h"; level: 1 | 2 | 3; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "p"; text: string };

const UL_RE = /^\s*[-*]\s+(.*)$/;
const OL_RE = /^\s*\d+\.\s+(.*)$/;
const H_RE = /^(#{1,3})\s+(.*)$/;

function parseBlocks(text: string): Block[] {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];

  const flushPara = () => {
    if (para.length) {
      blocks.push({ kind: "p", text: para.join("\n") });
      para = [];
    }
  };

  for (const line of lines) {
    if (line.trim() === "") {
      flushPara();
      continue;
    }
    const h = H_RE.exec(line);
    if (h) {
      flushPara();
      blocks.push({ kind: "h", level: h[1].length as 1 | 2 | 3, text: h[2] });
      continue;
    }
    const ul = UL_RE.exec(line);
    if (ul) {
      flushPara();
      const last = blocks[blocks.length - 1];
      if (last && last.kind === "ul") last.items.push(ul[1]);
      else blocks.push({ kind: "ul", items: [ul[1]] });
      continue;
    }
    const ol = OL_RE.exec(line);
    if (ol) {
      flushPara();
      const last = blocks[blocks.length - 1];
      if (last && last.kind === "ol") last.items.push(ol[1]);
      else blocks.push({ kind: "ol", items: [ol[1]] });
      continue;
    }
    para.push(line);
  }
  flushPara();
  return blocks;
}

function renderBlocks(text: string): ReactNode {
  return parseBlocks(text).map((b, i) => {
    switch (b.kind) {
      case "h": {
        const cls =
          b.level === 1
            ? "text-base font-semibold"
            : b.level === 2
              ? "text-sm font-semibold"
              : "text-sm font-semibold text-muted";
        return (
          <p key={i} className={cls}>
            {renderInline(b.text)}
          </p>
        );
      }
      case "ul":
        return (
          <ul key={i} className="list-disc space-y-1 pl-5">
            {b.items.map((it, j) => (
              <li key={j}>{renderInline(it)}</li>
            ))}
          </ul>
        );
      case "ol":
        return (
          <ol key={i} className="list-decimal space-y-1 pl-5">
            {b.items.map((it, j) => (
              <li key={j}>{renderInline(it)}</li>
            ))}
          </ol>
        );
      case "p":
        return (
          <p key={i} className="whitespace-pre-wrap break-words">
            {renderInline(b.text)}
          </p>
        );
    }
  });
}

// Inline: **bold** and `code`. Tokenises on the first matching delimiter, left to
// right, so unmatched delimiters render literally.
const INLINE_RE = /(\*\*([^*]+)\*\*|`([^`]+)`)/;

function renderInline(text: string): ReactNode {
  const out: ReactNode[] = [];
  let rest = text;
  let key = 0;
  while (rest.length) {
    const m = INLINE_RE.exec(rest);
    if (!m || m.index === undefined) {
      out.push(<Fragment key={key++}>{rest}</Fragment>);
      break;
    }
    if (m.index > 0) out.push(<Fragment key={key++}>{rest.slice(0, m.index)}</Fragment>);
    if (m[2] !== undefined) {
      out.push(<strong key={key++}>{m[2]}</strong>);
    } else if (m[3] !== undefined) {
      out.push(
        <code key={key++} className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[0.85em]">
          {m[3]}
        </code>,
      );
    }
    rest = rest.slice(m.index + m[0].length);
  }
  return out;
}
