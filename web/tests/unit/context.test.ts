import { shapeContextBlocks } from "@/lib/ai/context";
import type { SegmentMatch } from "@/lib/types/database";

describe("shapeContextBlocks", () => {
  it("maps retrieval rows into provider context blocks", () => {
    const rows: SegmentMatch[] = [
      {
        id: "seg-1",
        episode_id: "ep-1",
        chunk_start: 90,
        chunk_end: 150,
        text: "Tommy introduces a new wave of British heavy metal segment.",
        date: "1980-04-18",
        similarity: 0.76,
      },
    ];

    expect(shapeContextBlocks(rows)).toEqual([
      {
        date: "1980-04-18",
        chunkStart: 90,
        chunkEnd: 150,
        text: "Tommy introduces a new wave of British heavy metal segment.",
      },
    ]);
  });
});
