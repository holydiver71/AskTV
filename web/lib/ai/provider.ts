export type ContextBlock = {
  date: string;      // "YYYY-MM-DD"
  chunkStart: number | null; // seconds; null for metadata rows without a timestamp
  chunkEnd: number | null;
  text: string;
  sourceType?: "transcript" | "track" | "session";
};

export type Citation = {
  date: string;
  chunkStart: number | null;
  text: string;
  formatted: string;  // "[YYYY-MM-DD @ HH:MM:SS]"
};

export type GenerateResult = {
  answer: string;
  citations: Citation[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

/**
 * Abstraction over AI providers so the backend can swap between
 * OpenAI, Groq, or any other provider without touching the API route.
 */
export interface AIProvider {
  /** Embed a user query into a 512-dim vector. */
  embedQuery(text: string): Promise<number[]>;

  /** Generate a grounded Tommy Vance-style answer with inline citations. */
  generateAnswer(
    question: string,
    context: ContextBlock[],
    history: ChatMessage[]
  ): Promise<GenerateResult>;
}
