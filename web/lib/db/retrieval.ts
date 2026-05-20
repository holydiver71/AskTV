import { createClient } from "@supabase/supabase-js";
import type { SegmentMatch, UnifiedMatch } from "@/lib/types/database";

/**
 * Vector similarity search over transcript_segments using the
 * match_transcript_segments RPC function.
 *
 * Requires the following SQL function to exist in Supabase
 * (see web/supabase/match_segments.sql):
 *
 *   match_transcript_segments(query_embedding, match_count, match_threshold)
 */
export async function matchTranscriptSegments(
  queryEmbedding: number[],
  matchCount = 8,
  matchThreshold = 0.45
): Promise<SegmentMatch[]> {
  // Use the anon key — this is a read-only search and RLS is not a concern here.
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data, error } = await supabase.rpc("match_transcript_segments", {
    query_embedding: queryEmbedding,
    match_count: matchCount,
    match_threshold: matchThreshold,
  });

  if (!error) {
    return (data as SegmentMatch[]) ?? [];
  }

  // Backward compatibility for older DB deployments where the function
  // only accepts (query_embedding, match_count) and returns episode_date.
  if (isLegacySignatureError(error.message)) {
    const { data: legacyData, error: legacyError } = await supabase.rpc(
      "match_transcript_segments",
      {
        query_embedding: queryEmbedding,
        match_count: matchCount,
      }
    );

    if (legacyError) {
      console.error("matchTranscriptSegments legacy error:", legacyError);
      throw new Error(`Retrieval failed: ${legacyError.message}`);
    }

    return ((legacyData as LegacySegmentMatch[] | null) ?? []).map((row) => ({
      id: "",
      episode_id: "",
      chunk_start: row.chunk_start,
      chunk_end: row.chunk_end,
      text: row.text,
      date: row.episode_date,
      similarity: row.similarity,
    }));
  }

  console.error("matchTranscriptSegments error:", error);
  throw new Error(`Retrieval failed: ${error.message}`);
}

/**
 * Hybrid vector similarity search over both transcript_segments and
 * metadata_chunks using the match_hybrid RPC function.
 *
 * Requires the following SQL functions to exist in Supabase:
 *   - web/supabase/match_hybrid.sql
 *   - web/supabase/metadata_chunks.sql
 *
 * Falls back to matchTranscriptSegments (transcript-only) when the
 * match_hybrid function does not exist in the database, converting the
 * results to UnifiedMatch shape for caller compatibility.
 */
export async function matchHybrid(
  queryEmbedding: number[],
  queryText = "",
  matchCount = 12,
  matchThreshold = 0.35
): Promise<UnifiedMatch[]> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data, error } = await supabase.rpc("match_hybrid", {
    query_embedding: queryEmbedding,
    query_text: queryText,
    match_count: matchCount,
    match_threshold: matchThreshold,
  });

  if (!error) {
    return (data as UnifiedMatch[]) ?? [];
  }

  // If match_hybrid doesn't exist yet, fall back to transcript-only retrieval.
  if (isHybridFunctionMissingError(error.message)) {
    const segments = await matchTranscriptSegments(
      queryEmbedding,
      matchCount,
      matchThreshold
    );
    return segments.map((s) => ({
      ...s,
      source_type: "transcript" as const,
    }));
  }

  console.error("matchHybrid error:", error);
  throw new Error(`Retrieval failed: ${error.message}`);
}

type LegacySegmentMatch = {
  episode_date: string;
  chunk_start: number;
  chunk_end: number;
  text: string;
  similarity: number;
};

function isLegacySignatureError(message: string): boolean {
  return (
    message.includes("match_transcript_segments") &&
    message.includes("match_threshold")
  );
}

function isHybridFunctionMissingError(message: string): boolean {
  return message.includes("match_hybrid");
}
