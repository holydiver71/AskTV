import {
  extractCitations,
  formatCitation,
  formatMetadataCitation,
  formatTimestamp,
  stripCitations,
  type ContextBlock,
} from "@/lib/utils/citations";

describe("citation utilities", () => {
  it("formats timestamps as HH:MM:SS", () => {
    expect(formatTimestamp(0)).toBe("00:00:00");
    expect(formatTimestamp(61)).toBe("00:01:01");
    expect(formatTimestamp(3661)).toBe("01:01:01");
    expect(formatTimestamp(7322.99)).toBe("02:02:02");
  });

  it("formats canonical citation strings", () => {
    expect(formatCitation("1980-07-04", 125)).toBe("[1980-07-04 @ 00:02:05]");
  });

  it("formats metadata citation — track", () => {
    expect(formatMetadataCitation("1980-03-07", "track")).toBe(
      "[1980-03-07 \u2014 track listing]"
    );
  });

  it("formats metadata citation — session", () => {
    expect(formatMetadataCitation("1980-10-24", "session")).toBe(
      "[1980-10-24 \u2014 session]"
    );
  });

  it("extracts unique citations and enriches with matching context", () => {
    const context: ContextBlock[] = [
      {
        date: "1980-01-11",
        chunkStart: 120,
        chunkEnd: 180,
        text: "AC/DC live track and Tommy intro",
        sourceType: "transcript",
      },
      {
        date: "1980-02-22",
        chunkStart: 360,
        chunkEnd: 420,
        text: "Iron Maiden session mention",
        sourceType: "transcript",
      },
    ];

    const answer = [
      "Tommy played AC/DC [1980-01-11 @ 00:02:00].",
      "He also referenced Maiden [1980-02-22 @ 00:06:02].",
      "Duplicate marker should be ignored [1980-01-11 @ 00:02:00].",
    ].join(" ");

    expect(extractCitations(answer, context)).toEqual([
      {
        date: "1980-01-11",
        chunkStart: 120,
        text: "AC/DC live track and Tommy intro",
        formatted: "[1980-01-11 @ 00:02:00]",
      },
      {
        date: "1980-02-22",
        chunkStart: 362,
        text: "Iron Maiden session mention",
        formatted: "[1980-02-22 @ 00:06:02]",
      },
    ]);
  });

  it("keeps citation even when no close context block exists", () => {
    const citations = extractCitations("Unknown marker [1980-03-07 @ 01:00:00]", []);
    expect(citations).toEqual([
      {
        date: "1980-03-07",
        chunkStart: 3600,
        text: "",
        formatted: "[1980-03-07 @ 01:00:00]",
      },
    ]);
  });

  it("extracts metadata track listing citations", () => {
    const context: ContextBlock[] = [
      {
        date: "1980-03-07",
        chunkStart: null,
        chunkEnd: null,
        text: "1980-03-07. Artist: Genesis. Track: Duke's Travels.",
        sourceType: "track",
      },
    ];

    const answer = "Tommy played Genesis [1980-03-07 \u2014 track listing].";
    const citations = extractCitations(answer, context);

    expect(citations).toEqual([
      {
        date: "1980-03-07",
        chunkStart: null,
        text: "1980-03-07. Artist: Genesis. Track: Duke's Travels.",
        formatted: "[1980-03-07 \u2014 track listing]",
      },
    ]);
  });

  it("extracts metadata session citations", () => {
    const context: ContextBlock[] = [
      {
        date: "1980-10-24",
        chunkStart: null,
        chunkEnd: null,
        text: "1980-10-24. Session artist: Saxon.",
        sourceType: "session",
      },
    ];

    const answer = "Saxon featured in a session [1980-10-24 \u2014 session].";
    const citations = extractCitations(answer, context);

    expect(citations).toEqual([
      {
        date: "1980-10-24",
        chunkStart: null,
        text: "1980-10-24. Session artist: Saxon.",
        formatted: "[1980-10-24 \u2014 session]",
      },
    ]);
  });

  it("strips both timed and metadata citation markers", () => {
    const text =
      "Answer text [1980-03-07 @ 01:00:00] and more [1980-03-07 \u2014 track listing].";
    expect(stripCitations(text)).toBe("Answer text and more.");
  });

  it("deduplicates metadata citations", () => {
    const answer =
      "Genesis [1980-03-07 \u2014 track listing] again [1980-03-07 \u2014 track listing].";
    const citations = extractCitations(answer, []);
    expect(citations).toHaveLength(1);
    expect(citations[0].formatted).toBe("[1980-03-07 \u2014 track listing]");
  });
});
