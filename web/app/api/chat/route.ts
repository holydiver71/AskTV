import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { OpenAIProvider } from "@/lib/ai/openai-provider";
import { matchHybrid, searchEpisodeByFts } from "@/lib/db/retrieval";
import type { UnifiedMatch } from "@/lib/types/database";
import { shapeContextBlocks } from "@/lib/ai/context";
import {
  extractCitations,
  formatCitation,
  formatMetadataCitation,
} from "@/lib/utils/citations";
import type { ContextBlock, Citation } from "@/lib/utils/citations";

const requestSchema = z.object({
  message: z.string().min(1).max(1000),
  history: z
    .array(
      z.object({
        role: z.enum(["user", "assistant"]),
        content: z.string(),
      })
    )
    .max(20)
    .default([]),
});

const NO_CONTEXT_REPLY =
  "I'm afraid that's not something I can find in the archive right now.";

// Lazy singleton — only instantiated on first request, not at build time.
let provider: OpenAIProvider | null = null;
function getProvider(): OpenAIProvider {
  if (!provider) provider = new OpenAIProvider();
  return provider;
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "invalid_request", message: "Invalid JSON body." },
      { status: 400 }
    );
  }

  const parsed = requestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "invalid_request", message: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const { message, history } = parsed.data;

  try {
    // 1. Embed the user question.
    const embedding = await getProvider().embedQuery(message);

    // 2. Retrieve the most relevant transcript and metadata matches.
    let matches: UnifiedMatch[];
    try {
      const ftsKeywords = extractFtsKeywords(message);
      matches = await matchHybrid(embedding, ftsKeywords, 12, 0.35);

      // When the query names a specific date, guarantee that episode's
      // transcript chunks are included even if they were crowded out of
      // the hybrid search's LIMIT by higher-scoring metadata vectors.
      if (ftsKeywords.length >= 3) {
        const mentionedDate = extractMentionedDate(message);
        if (mentionedDate) {
          const episodeFts = await searchEpisodeByFts(mentionedDate, ftsKeywords, 4);
          if (episodeFts.length > 0) {
            const seenIds = new Set(matches.map((m) => m.id));
            const newChunks = episodeFts.filter((m) => !seenIds.has(m.id));
            // Prepend so they appear early in context (higher priority)
            matches = [...newChunks, ...matches];
          }
        }
      }
    } catch (err) {
      if (isMissingRetrievalFunctionError(err)) {
        return NextResponse.json(
          {
            error: "retrieval_not_configured",
            message:
              "Ask Tommy search is not configured yet. Run web/supabase/match_segments.sql in Supabase SQL Editor, then retry.",
          },
          { status: 503 }
        );
      }
      throw err;
    }

    // 3. For temporal-superlative queries ("first", "debut", "last", etc.),
    //    re-rank metadata chunks by episode date so the chronologically
    //    correct episode leads context — not just whichever repeat has the
    //    richest metadata text and therefore the highest vector score.
    const temporalIntent = detectTemporalIntent(message);
    if (temporalIntent) {
      matches = applyTemporalReRank(matches, temporalIntent);
    }

    // 4. Shape matches into context blocks.
    const context = shapeContextBlocks(matches);

    // 5. Generate the grounded Tommy Vance answer.
    const result = await getProvider().generateAnswer(message, context, history);

    const enriched = ensureAnswerHasCitations(result.answer, result.citations, context);

    return NextResponse.json({
      answer: enriched.answer,
      citations: enriched.citations,
    });
  } catch (err: unknown) {
    if (isProviderTimeoutError(err)) {
      return NextResponse.json(
        {
          error: "provider_timeout",
          message: "Ask Tommy is taking too long to respond — please retry.",
        },
        { status: 504 }
      );
    }

    // OpenAI quota exceeded → friendly 429 response.
    if (isQuotaError(err)) {
      return NextResponse.json(
        {
          error: "quota_exceeded",
          message:
            "Ask Tommy is temporarily unavailable — please try again later.",
        },
        { status: 429 }
      );
    }

    console.error("[/api/chat] Unhandled error:", err);
    return NextResponse.json(
      { error: "internal_error", message: "An unexpected error occurred." },
      { status: 500 }
    );
  }
}

function isQuotaError(err: unknown): boolean {
  if (typeof err !== "object" || err === null) return false;
  const e = err as Record<string, unknown>;
  return e.status === 429 || (typeof e.code === "string" && e.code === "insufficient_quota");
}

function isMissingRetrievalFunctionError(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  return (
    err.message.includes("match_transcript_segments") ||
    err.message.includes("match_hybrid")
  );
}

/**
 * Strip dates, question words, and common stop words from a user message so
 * the remainder can be used as a PostgreSQL full-text search query.
 *
 * e.g. "who won the record token on 29/08/1980?" → "record token"
 */
const MONTH_NAMES: Record<string, string> = {
  january: "01", jan: "01",
  february: "02", feb: "02",
  march: "03", mar: "03",
  april: "04", apr: "04",
  may: "05",
  june: "06", jun: "06",
  july: "07", jul: "07",
  august: "08", aug: "08",
  september: "09", sep: "09", sept: "09",
  october: "10", oct: "10",
  november: "11", nov: "11",
  december: "12", dec: "12",
};

const MONTH_PATTERN =
  "january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec";

/**
 * Parse a specific date mentioned in the user's message and return it
 * as YYYY-MM-DD. Handles natural language ("4 January 1980", "January 4th 1980"),
 * DD/MM/YYYY, D/M/YYYY, and ISO YYYY-MM-DD.
 */
function extractMentionedDate(message: string): string | null {
  // Natural language day-first: "4 January 1980", "4th Jan 1980"
  const nlDmyMatch = message.match(
    new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+(${MONTH_PATTERN})\\s+(\\d{4})\\b`, "i")
  );
  if (nlDmyMatch) {
    const [, d, monthStr, y] = nlDmyMatch;
    const m = MONTH_NAMES[monthStr.toLowerCase()];
    if (m) return `${y}-${m}-${d.padStart(2, "0")}`;
  }
  // Natural language month-first: "January 4, 1980", "January 4th 1980"
  const nlMdyMatch = message.match(
    new RegExp(`\\b(${MONTH_PATTERN})\\s+(\\d{1,2})(?:st|nd|rd|th)?,?\\s+(\\d{4})\\b`, "i")
  );
  if (nlMdyMatch) {
    const [, monthStr, d, y] = nlMdyMatch;
    const m = MONTH_NAMES[monthStr.toLowerCase()];
    if (m) return `${y}-${m}-${d.padStart(2, "0")}`;
  }
  // DD/MM/YYYY or D/M/YYYY (including . and - separators)
  const dmyMatch = message.match(
    /\b(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{4})\b/
  );
  if (dmyMatch) {
    const [, d, m, y] = dmyMatch;
    return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }
  // YYYY-MM-DD
  const isoMatch = message.match(
    /\b(\d{4})[\/.\-](\d{1,2})[\/.\-](\d{1,2})\b/
  );
  if (isoMatch) {
    const [, y, m, d] = isoMatch;
    return `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
  }
  return null;
}

function extractFtsKeywords(message: string): string {
  return message
    // Remove dates: DD/MM/YYYY, MM-DD-YYYY, YYYY-MM-DD, bare years
    .replace(/\b\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{2,4}\b/g, "")
    .replace(/\b\d{4}[\/.\-]\d{1,2}[\/.\-]\d{1,2}\b/g, "")
    .replace(/\b(19|20)\d{2}\b/g, "")
    // Remove month names (already captured by extractMentionedDate)
    .replace(new RegExp(`\\b(${MONTH_PATTERN})\\b`, "gi"), "")
    // Remove common question / auxiliary words
    .replace(
      /\b(who|what|when|where|why|how|did|does|was|were|is|are|has|have|had|been|be|the|a|an|on|in|at|for|of|to|from|by|with|get|got|win|won|play|played|broadcast|show|episode|date|about|can|could|would|should|do|i|me|my|you|your)\b/gi,
      ""
    )
    // Collapse whitespace and strip punctuation
    .replace(/[?!.,;:"']/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function isProviderTimeoutError(err: unknown): boolean {
  if (typeof err !== "object" || err === null) return false;
  const e = err as Record<string, unknown>;
  const code = typeof e.code === "string" ? e.code : "";
  const name = typeof e.name === "string" ? e.name : "";
  const message = typeof e.message === "string" ? e.message : "";

  return (
    code === "ETIMEDOUT" ||
    code === "ECONNABORTED" ||
    name === "AbortError" ||
    message.toLowerCase().includes("timeout")
  );
}

/**
 * Returns "earliest" when the query asks about a first/debut appearance,
 * "latest" for a last/most-recent query, and null otherwise.
 */
function detectTemporalIntent(message: string): "earliest" | "latest" | null {
  const lower = message.toLowerCase();
  if (/\b(first|earliest|debut|originally)\b/.test(lower)) return "earliest";
  if (/\b(last|latest|most recent|final|newest)\b/.test(lower)) return "latest";
  return null;
}

/**
 * Re-rank session and track metadata chunks by episode date so temporal
 * queries surface the chronologically correct episode rather than whichever
 * repeat has the highest vector similarity score. Transcript chunks stay in
 * their original (similarity-ranked) order and follow the sorted metadata.
 */
function applyTemporalReRank(
  matches: UnifiedMatch[],
  intent: "earliest" | "latest"
): UnifiedMatch[] {
  const transcripts = matches.filter((m) => m.source_type === "transcript");
  const metadata = matches.filter((m) => m.source_type !== "transcript");
  const sorted = [...metadata].sort((a, b) => {
    const cmp = a.date.localeCompare(b.date);
    return intent === "earliest" ? cmp : -cmp;
  });
  return [...sorted, ...transcripts];
}

function ensureAnswerHasCitations(
  answer: string,
  citations: Citation[],
  context: ContextBlock[]
) {
  if (citations.length > 0) {
    return { answer, citations };
  }

  if (context.length === 0 || answer.includes(NO_CONTEXT_REPLY)) {
    return { answer, citations };
  }

  // Safety net: append up to two nearest context citations when the model
  // forgot to include inline citation markers.
  const fallbackCitations = context.slice(0, 2).map((c) => {
    if (c.chunkStart !== null) {
      return formatCitation(c.date, c.chunkStart);
    }
    const sourceType = c.sourceType === "session" ? "session" : "track";
    return formatMetadataCitation(c.date, sourceType);
  });
  const answerWithCitations = `${answer.trim()} ${fallbackCitations.join(" ")}`.trim();
  const extracted = extractCitations(answerWithCitations, context);

  return {
    answer: answerWithCitations,
    citations: extracted,
  };
}
