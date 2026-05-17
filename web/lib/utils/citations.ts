export type ContextBlock = {
  date: string;
  chunkStart: number;
  chunkEnd: number;
  text: string;
};

export type Citation = {
  date: string;
  chunkStart: number;
  text: string;
  formatted: string;
};

/** Convert seconds to HH:MM:SS broadcast-timestamp string. */
export function formatTimestamp(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** Produce a citation string in the canonical [YYYY-MM-DD @ HH:MM:SS] format. */
export function formatCitation(date: string, chunkStart: number): string {
  return `[${date} @ ${formatTimestamp(chunkStart)}]`;
}

const CITATION_RE = /\[(\d{4}-\d{2}-\d{2})\s*@\s*(\d{2}:\d{2}:\d{2})\]/g;

/**
 * Parse inline citation markers from an AI answer and enrich them with the
 * matching context block text where possible.
 */
export function extractCitations(
  text: string,
  contextBlocks: ContextBlock[]
): Citation[] {
  const seen = new Set<string>();
  const citations: Citation[] = [];
  let match: RegExpExecArray | null;

  while ((match = CITATION_RE.exec(text)) !== null) {
    const formatted = match[0];
    if (seen.has(formatted)) continue;
    seen.add(formatted);

    const date = match[1];
    const [h, m, s] = match[2].split(":").map(Number);
    const chunkStart = h * 3600 + m * 60 + s;

    // Find the closest context block for this date (within ±30s tolerance).
    const block = contextBlocks.find(
      (b) => b.date === date && Math.abs(b.chunkStart - chunkStart) < 30
    );

    citations.push({ date, chunkStart, text: block?.text ?? "", formatted });
  }

  return citations;
}
