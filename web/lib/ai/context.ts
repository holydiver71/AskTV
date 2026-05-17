import type { SegmentMatch } from "@/lib/types/database";
import type { ContextBlock } from "@/lib/ai/provider";

export function shapeContextBlocks(matches: SegmentMatch[]): ContextBlock[] {
  return matches.map((m) => ({
    date: m.date,
    chunkStart: m.chunk_start,
    chunkEnd: m.chunk_end,
    text: m.text,
  }));
}