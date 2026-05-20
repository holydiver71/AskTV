import { shapeContextBlocks } from "@/lib/ai/context";
import type { SegmentMatch, UnifiedMatch } from "@/lib/types/database";

describe("shapeContextBlocks", () => {
  it("maps SegmentMatch rows into context blocks with transcript sourceType", () => {
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
        sourceType: "transcript",
      },
    ]);
  });

  it("maps UnifiedMatch transcript rows into context blocks", () => {
    const rows: UnifiedMatch[] = [
      {
        id: "seg-2",
        episode_id: "ep-2",
        source_type: "transcript",
        chunk_start: 120,
        chunk_end: 180,
        text: "AC/DC blasting out of the speakers.",
        date: "1980-06-06",
        similarity: 0.82,
      },
    ];

    expect(shapeContextBlocks(rows)).toEqual([
      {
        date: "1980-06-06",
        chunkStart: 120,
        chunkEnd: 180,
        text: "AC/DC blasting out of the speakers.",
        sourceType: "transcript",
      },
    ]);
  });

  it("maps UnifiedMatch track rows with null timestamps", () => {
    const rows: UnifiedMatch[] = [
      {
        id: "meta-1",
        episode_id: "ep-3",
        source_type: "track",
        chunk_start: null,
        chunk_end: null,
        text: "1980-03-07. Artist: Genesis. Track: Duke's Travels. Details: LP-Duke.",
        date: "1980-03-07",
        similarity: 0.79,
      },
    ];

    expect(shapeContextBlocks(rows)).toEqual([
      {
        date: "1980-03-07",
        chunkStart: null,
        chunkEnd: null,
        text: "1980-03-07. Artist: Genesis. Track: Duke's Travels. Details: LP-Duke.",
        sourceType: "track",
      },
    ]);
  });

  it("maps UnifiedMatch session rows", () => {
    const rows: UnifiedMatch[] = [
      {
        id: "meta-2",
        episode_id: "ep-4",
        source_type: "session",
        chunk_start: null,
        chunk_end: null,
        text: "1980-10-24. Session artist: Saxon. Details: Live session.",
        date: "1980-10-24",
        similarity: 0.71,
      },
    ];

    expect(shapeContextBlocks(rows)).toEqual([
      {
        date: "1980-10-24",
        chunkStart: null,
        chunkEnd: null,
        text: "1980-10-24. Session artist: Saxon. Details: Live session.",
        sourceType: "session",
      },
    ]);
  });
});
