/**
 * Deterministic speech-text presentation (Capstone P7 / E5, §24/§25/§26).
 *
 * Turns candidate-visible Markdown-ish text into clean text suitable for TTS WITHOUT any
 * model call. It removes presentation SYNTAX only (never substantive caveats/evidence),
 * avoids reading long raw URLs aloud, and replaces a citation/sources block with a short
 * spoken note ("Sources are available on screen."). Sources remain fully visible in the UI.
 */

const SOURCES_NOTE_FALLBACK = "Sources are available on screen.";

export interface SpeechTextOptions {
  /** Localised "sources on screen" note; falls back to English. */
  sourcesNote?: string;
  /** Soft character cap; longer text is NOT silently truncated — callers gate long detail. */
  maxChars?: number;
}

/** Convert visible response/question text to spoken text. Pure + deterministic. */
export function toSpeechText(input: string, opts: SpeechTextOptions = {}): string {
  const sourcesNote = opts.sourcesNote || SOURCES_NOTE_FALLBACK;
  let text = input ?? "";

  // Markdown links [label](url) → label (never read the URL aloud).
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
  // Bare URLs → drop (a human-readable label already precedes them in practice).
  text = text.replace(/https?:\/\/\S+/g, "");
  // Inline code / code fences → keep the inner text, drop backticks.
  text = text.replace(/```[a-z]*\n?/gi, "").replace(/`([^`]*)`/g, "$1");
  // Headings, blockquotes, list bullets → strip the leading markers only.
  text = text.replace(/^\s{0,3}#{1,6}\s+/gm, "");
  text = text.replace(/^\s{0,3}>\s?/gm, "");
  text = text.replace(/^\s{0,3}[-*+]\s+/gm, "");
  text = text.replace(/^\s{0,3}\d+\.\s+/gm, "");
  // Bold/italic/strikethrough markers → keep the words.
  text = text.replace(/(\*\*|__)(.*?)\1/g, "$2");
  text = text.replace(/(\*|_)(.*?)\1/g, "$2");
  text = text.replace(/~~(.*?)~~/g, "$1");
  // Citation markers like [1] [2] → spoken sources note (once), keeping the sentence.
  const hadCitations = /\[\d+\]/.test(text);
  text = text.replace(/\[\d+\]/g, "");

  // Collapse whitespace.
  text = text.replace(/[ \t]+/g, " ").replace(/\n{2,}/g, "\n").trim();

  if (hadCitations) {
    text = text ? `${text} ${sourcesNote}` : sourcesNote;
  }

  const cap = opts.maxChars ?? 0;
  if (cap > 0 && text.length > cap) {
    // Do not silently lose content: cut at a sentence boundary and signal there is more.
    const head = text.slice(0, cap);
    const lastStop = Math.max(head.lastIndexOf(". "), head.lastIndexOf("! "), head.lastIndexOf("? "));
    text = (lastStop > cap * 0.5 ? head.slice(0, lastStop + 1) : head).trim();
  }
  return text;
}
