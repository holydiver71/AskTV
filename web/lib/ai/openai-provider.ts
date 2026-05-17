import OpenAI from "openai";
import type {
  AIProvider,
  ContextBlock,
  ChatMessage,
  GenerateResult,
} from "./provider";
import { formatTimestamp, extractCitations } from "@/lib/utils/citations";
import { getChatSystemPrompt } from "@/lib/ai/system-prompt";

const SYSTEM_PROMPT = getChatSystemPrompt();

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
      temperature: 0.55,
      max_tokens: 600,
    });

    const answer = completion.choices[0]?.message?.content ?? "";
    const citations = extractCitations(answer, context);

    return { answer, citations };
  }
}
