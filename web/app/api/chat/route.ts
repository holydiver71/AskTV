import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { OpenAIProvider } from "@/lib/ai/openai-provider";
import { matchHybrid } from "@/lib/db/retrieval";
import { shapeContextBlocks } from "@/lib/ai/context";
import {
  extractCitations,
  formatCitation,
  formatMetadataCitation,
} from "@/lib/utils/citations";

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
    let matches;
    try {
        matches = await matchHybrid(embedding, 12, 0.35);
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

    // 3. Shape matches into context blocks.
    const context = shapeContextBlocks(matches);

    // 4. Generate the grounded Tommy Vance answer.
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

function ensureAnswerHasCitations(
  answer: string,
  citations: Array<{ date: string; chunkStart: number | null; text: string; formatted: string }>,
  context: Array<{ date: string; chunkStart: number | null; chunkEnd: number | null; text: string; sourceType?: string }>
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
