export type ContextBlock = {
  date: string;
  chunkStart: number | null; // null for metadata rows without a timestamp
  chunkEnd: number | null;
  text: string;
  sourceType?: "transcript" | "track" | "session";
};

export type Citation = {
  date: string;
  chunkStart: number | null;
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

/**
 * Produce a citation for a metadata row (track or session) that has no
 * verified timestamp.  Format: [YYYY-MM-DD — track listing] or
 * [YYYY-MM-DD — session].
 */
export function formatMetadataCitation(
  date: string,
  sourceType: "track" | "session"
): string {
  const label = sourceType === "track" ? "track listing" : "session";
  return `[${date} \u2014 ${label}]`;
}

// Matches [YYYY-MM-DD @ HH:MM:SS] — transcript/timed citations
const CITATION_RE = /\[(\d{4}-\d{2}-\d{2})\s*@\s*(\d{2}:\d{2}:\d{2})\]/g;

// Matches [YYYY-MM-DD — track listing] or [YYYY-MM-DD — session]
const METADATA_CITATION_RE =
  /\[(\d{4}-\d{2}-\d{2})\s*\u2014\s*(track listing|session)\]/g;

/** Remove inline citation markers from a string, leaving surrounding text intact. */
export function stripCitations(text: string): string {
  return text
    .replace(/\s*\[\d{4}-\d{2}-\d{2}\s*@\s*\d{2}:\d{2}:\d{2}\]/g, "")
    .replace(/\s*\[\d{4}-\d{2}-\d{2}\s*\u2014\s*(?:track listing|session)\]/g, "")
    .trim();
}

/**
 * Parse inline citation markers from an AI answer and enrich them with the
 * matching context block text where possible.
 *
 * Handles both timed citations ([YYYY-MM-DD @ HH:MM:SS]) and metadata
 * citations ([YYYY-MM-DD — track listing] / [YYYY-MM-DD — session]).
 */
export function extractCitations(
  text: string,
  contextBlocks: ContextBlock[]
): Citation[] {
  const seen = new Set<string>();
  const citations: Citation[] = [];
  let match: RegExpExecArray | null;

  // Reset lastIndex before iterating (regexes are stateful when using /g)
  CITATION_RE.lastIndex = 0;
  METADATA_CITATION_RE.lastIndex = 0;

  // --- timed citations ---
  while ((match = CITATION_RE.exec(text)) !== null) {
    const formatted = match[0];
    if (seen.has(formatted)) continue;
    seen.add(formatted);

    const date = match[1];
    const [h, m, s] = match[2].split(":").map(Number);
    const chunkStart = h * 3600 + m * 60 + s;

    // Find the closest context block for this date (within ±30s tolerance).
    const block = contextBlocks.find(
      (b) =>
        b.date === date &&
        b.chunkStart !== null &&
        Math.abs(b.chunkStart - chunkStart) < 30
    );

    citations.push({ date, chunkStart, text: block?.text ?? "", formatted });
  }

  // --- metadata citations ---
  while ((match = METADATA_CITATION_RE.exec(text)) !== null) {
    const formatted = match[0];
    if (seen.has(formatted)) continue;
    seen.add(formatted);

    const date = match[1];
    const block = contextBlocks.find(
      (b) => b.date === date && b.chunkStart === null
    );

    citations.push({
      date,
      chunkStart: null,
      text: block?.text ?? "",
      formatted,
    });
  }

  return citations;
}

