import type { SegmentMatch, UnifiedMatch } from "@/lib/types/database";
import type { ContextBlock } from "@/lib/ai/provider";

/**
 * Shape retrieval results into provider context blocks.
 * Accepts either a legacy SegmentMatch[] (transcript-only) or the new
 * UnifiedMatch[] (hybrid transcript + metadata).
 */
export function shapeContextBlocks(
  matches: UnifiedMatch[] | SegmentMatch[]
): ContextBlock[] {
  return matches.map((m) => {
    // UnifiedMatch has source_type; SegmentMatch does not
    const sourceType = "source_type" in m ? m.source_type : "transcript";
    return {
      date: m.date,
      chunkStart: m.chunk_start,
      chunkEnd: m.chunk_end,
      text: m.text,
      sourceType,
    };
  });
}