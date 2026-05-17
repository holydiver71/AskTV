import OpenAI from "openai";
import type {
  AIProvider,
  ContextBlock,
  ChatMessage,
  GenerateResult,
} from "./provider";
import { formatTimestamp, extractCitations } from "@/lib/utils/citations";

const SYSTEM_PROMPT = `\
You are Tommy Vance, the legendary host of BBC Radio 1's Friday Rock Show (1978–1993). \
You have encyclopaedic knowledge of rock music, classic albums, and BBC sessions.

Answer questions in Tommy's warm, enthusiastic, knowledgeable broadcasting style — \
conversational, passionate about rock, with natural radio phrasing.

RULES — follow these precisely:
1. Only use information from the ARCHIVE CONTEXT provided below.
2. Every factual claim about a show date, track, artist, or session MUST be cited inline \
   using exactly this format: [YYYY-MM-DD @ HH:MM:SS]
3. If the answer is not in the provided context, say: \
   "I'm afraid that's not something I can find in the archive right now."
4. Do not invent dates, tracks, or artists.
5. Keep answers concise — two to four sentences where possible.`;

export class OpenAIProvider implements AIProvider {
  private client: OpenAI;

  constructor() {
    this.client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  }

  async embedQuery(text: string): Promise<number[]> {
    const response = await this.client.embeddings.create({
      model: "text-embedding-3-small",
      input: text,
      dimensions: 512,
    });
    return response.data[0].embedding;
  }

  async generateAnswer(
    question: string,
    context: ContextBlock[],
    history: ChatMessage[]
  ): Promise<GenerateResult> {
    const contextText =
      context.length > 0
        ? context
            .map(
              (c) =>
                `[${c.date} @ ${formatTimestamp(c.chunkStart)}]\n${c.text}`
            )
            .join("\n\n---\n\n")
        : "(No archive context found for this query.)";

    const messages: OpenAI.ChatCompletionMessageParam[] = [
      {
        role: "system",
        content: `${SYSTEM_PROMPT}\n\nARCHIVE CONTEXT:\n${contextText}`,
      },
      ...history
        .slice(-8)
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content })),
      { role: "user", content: question },
    ];

    const completion = await this.client.chat.completions.create({
      model: "gpt-4o-mini",
      messages,
      temperature: 0.4,
      max_tokens: 600,
    });

    const answer = completion.choices[0]?.message?.content ?? "";
    const citations = extractCitations(answer, context);

    return { answer, citations };
  }
}
