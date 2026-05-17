import { describe, expect, it, vi, beforeEach } from "vitest";

const embedQueryMock = vi.fn<() => Promise<number[]>>();
const generateAnswerMock = vi.fn<
  () => Promise<{ answer: string; citations: Array<{ formatted: string }> }>
>();
const matchTranscriptSegmentsMock = vi.fn<() => Promise<Array<Record<string, unknown>>>>();

vi.mock("@/lib/ai/openai-provider", () => {
  class MockOpenAIProvider {
    embedQuery = embedQueryMock;
    generateAnswer = generateAnswerMock;
  }

  return {
    OpenAIProvider: MockOpenAIProvider,
  };
});

vi.mock("@/lib/db/retrieval", () => ({
  matchTranscriptSegments: matchTranscriptSegmentsMock,
}));

async function postJson(body: unknown) {
  const { POST } = await import("@/app/api/chat/route");
  const request = new Request("http://localhost/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  return POST(request as never);
}

describe("POST /api/chat", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    embedQueryMock.mockReset();
    generateAnswerMock.mockReset();
    matchTranscriptSegmentsMock.mockReset();
  });

  it("returns 400 for invalid JSON", async () => {
    const { POST } = await import("@/app/api/chat/route");
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{bad-json",
    });

    const response = await POST(request as never);
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "invalid_request",
    });
  });

  it("returns 400 for schema validation errors", async () => {
    const response = await postJson({ message: "" });
    expect(response.status).toBe(400);

    await expect(response.json()).resolves.toMatchObject({
      error: "invalid_request",
    });
  });

  it("returns 200 with answer and citations", async () => {
    embedQueryMock.mockResolvedValue([0.1, 0.2, 0.3]);
    matchTranscriptSegmentsMock.mockResolvedValue([
      {
        id: "seg-1",
        episode_id: "ep-1",
        chunk_start: 420,
        chunk_end: 480,
        text: "Motorhead track and DJ chat",
        date: "1980-08-01",
        similarity: 0.81,
      },
    ]);
    generateAnswerMock.mockResolvedValue({
      answer: "Tommy played Motorhead [1980-08-01 @ 00:07:00]",
      citations: [{ formatted: "[1980-08-01 @ 00:07:00]" }],
    });

    const response = await postJson({ message: "When did he play Motorhead?", history: [] });
    expect(response.status).toBe(200);

    await expect(response.json()).resolves.toEqual({
      answer: "Tommy played Motorhead [1980-08-01 @ 00:07:00]",
      citations: [{ formatted: "[1980-08-01 @ 00:07:00]" }],
    });

    expect(embedQueryMock).toHaveBeenCalledWith("When did he play Motorhead?");
    expect(matchTranscriptSegmentsMock).toHaveBeenCalledWith([0.1, 0.2, 0.3], 12, 0.35);
    expect(generateAnswerMock).toHaveBeenCalledWith(
      "When did he play Motorhead?",
      [
        {
          date: "1980-08-01",
          chunkStart: 420,
          chunkEnd: 480,
          text: "Motorhead track and DJ chat",
        },
      ],
      []
    );
  });

  it("returns 429 for quota errors", async () => {
    embedQueryMock.mockResolvedValue([0.9]);
    matchTranscriptSegmentsMock.mockResolvedValue([]);
    generateAnswerMock.mockRejectedValue({ status: 429 });

    const response = await postJson({ message: "test", history: [] });
    expect(response.status).toBe(429);
    await expect(response.json()).resolves.toMatchObject({ error: "quota_exceeded" });
  });

  it("appends fallback citations when provider returns none", async () => {
    embedQueryMock.mockResolvedValue([0.5]);
    matchTranscriptSegmentsMock.mockResolvedValue([
      {
        id: "seg-1",
        episode_id: "ep-1",
        chunk_start: 75,
        chunk_end: 120,
        text: "Tommy intro mentioning session details",
        date: "1980-05-09",
        similarity: 0.77,
      },
    ]);
    generateAnswerMock.mockResolvedValue({
      answer: "Tommy mentioned a key session that night.",
      citations: [],
    });

    const response = await postJson({ message: "test", history: [] });
    expect(response.status).toBe(200);

    await expect(response.json()).resolves.toMatchObject({
      answer: expect.stringContaining("[1980-05-09 @ 00:01:15]"),
      citations: [
        expect.objectContaining({ formatted: "[1980-05-09 @ 00:01:15]" }),
      ],
    });
  });

  it("returns 504 for provider timeout errors", async () => {
    embedQueryMock.mockResolvedValue([0.9]);
    matchTranscriptSegmentsMock.mockResolvedValue([]);
    generateAnswerMock.mockRejectedValue({ code: "ETIMEDOUT", message: "request timeout" });

    const response = await postJson({ message: "test", history: [] });
    expect(response.status).toBe(504);
    await expect(response.json()).resolves.toMatchObject({ error: "provider_timeout" });
  });

  it("returns 500 for unhandled provider errors", async () => {
    embedQueryMock.mockResolvedValue([0.9]);
    matchTranscriptSegmentsMock.mockResolvedValue([]);
    generateAnswerMock.mockRejectedValue(new Error("unexpected"));

    const response = await postJson({ message: "test", history: [] });
    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toMatchObject({ error: "internal_error" });
  });
});
