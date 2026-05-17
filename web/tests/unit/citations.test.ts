import {
  extractCitations,
  formatCitation,
  formatTimestamp,
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

  it("extracts unique citations and enriches with matching context", () => {
    const context: ContextBlock[] = [
      {
        date: "1980-01-11",
        chunkStart: 120,
        chunkEnd: 180,
        text: "AC/DC live track and Tommy intro",
      },
      {
        date: "1980-02-22",
        chunkStart: 360,
        chunkEnd: 420,
        text: "Iron Maiden session mention",
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
});
