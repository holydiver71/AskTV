"use client";

import { useState, useRef, useEffect, forwardRef } from "react";
import { useSearchParams } from "next/navigation";
import Image from "next/image";
import { CitationChip } from "@/components/citation-chip";
import { stripCitations } from "@/lib/utils/citations";
import type { Citation } from "@/lib/utils/citations";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

const SUGGESTED_PROMPTS = [
  "What AC/DC session did Tommy play in 1980?",
  "When did Iron Maiden first appear on the Friday Rock Show?",
  "What tracks did Motörhead have in 1980?",
  "Which bands had BBC sessions in the first half of 1980?",
];

export default function ChatPage() {
  const searchParams = useSearchParams();
  const sessionKey = searchParams.get("t");

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const shouldRefocusInput = useRef(false);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    setMessages([]);
    setInput("");
  }, [sessionKey]);

  useEffect(() => {
    if (hasMessages) {
      const reduceMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;
      bottomRef.current?.scrollIntoView({
        behavior: reduceMotion ? "auto" : "smooth",
      });
    }
  }, [messages, hasMessages]);

  useEffect(() => {
    if (isLoading || !shouldRefocusInput.current) return;
    shouldRefocusInput.current = false;

    const frame = window.requestAnimationFrame(() => {
      const el = inputRef.current;
      if (!el) return;
      el.focus();
      const end = el.value.length;
      el.setSelectionRange(end, end);
    });

    return () => window.cancelAnimationFrame(frame);
  }, [isLoading, hasMessages, messages.length]);

  async function handleSubmit(question?: string) {
    const text = (question ?? input).trim();
    if (!text || isLoading) return;

    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text },
    ]);
    setInput("");
    setIsLoading(true);

    try {
      const history = messages
        .slice(-8)
        .map(({ role, content }) => ({ role, content }));

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });

      const data = await res.json();

      if (!res.ok) {
        const content =
          res.status === 429
            ? "Ask Tommy is temporarily unavailable — please try again later."
            : data.message ?? "Something went wrong. Please try again.";
        setMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: "assistant", content },
        ]);
        return;
      }

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.answer,
          citations: data.citations ?? [],
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Couldn't reach the server. Please check your connection.",
        },
      ]);
    } finally {
      shouldRefocusInput.current = true;
      setIsLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <section className="flex flex-col flex-1 min-h-0" aria-label="Ask Tommy chat">
      {!hasMessages ? (
        /* ── Hero — first view ───────────────────────────────── */
        <div className="flex flex-col flex-1 items-center justify-center px-4 py-12 gap-6 animate-hero-reveal">
          <div
            className="relative w-44 h-60 md:w-52 md:h-72 rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10"
            tabIndex={0}
            role="img"
            aria-label="Portrait of Tommy Vance"
          >
            <Image
              src="/tommyvance.png"
              alt=""
              fill
              sizes="(min-width: 768px) 208px, 176px"
              className="object-cover object-top"
              priority
            />
          </div>

          <div className="text-center space-y-1">
            <h1 className="text-2xl font-bold tracking-tight">Tommy Vance</h1>
            <p className="text-muted-foreground text-sm">
              The Friday Rock Show Archive · Ask me anything about the shows
            </p>
            <p className="text-xs text-amber-300/90">
              Temporary note: only 1980 episodes are currently available to
              research.
            </p>
          </div>

          <div className="w-full max-w-xl space-y-3">
            <QueryInput
              ref={inputRef}
              value={input}
              onChange={setInput}
              onSubmit={() => handleSubmit()}
              onKeyDown={handleKeyDown}
              isLoading={isLoading}
              inputLabel="Ask Tommy a question"
              submitLabel="Submit question"
            />
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => handleSubmit(p)}
                  disabled={isLoading}
                  aria-label={`Use suggested prompt: ${p}`}
                  className="text-xs min-h-11 px-4 py-2 rounded-full bg-muted hover:bg-muted/70 text-muted-foreground transition-colors disabled:opacity-50"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        /* ── Conversation view ───────────────────────────────── */
        <>
          {/* Message list */}
          <div className="flex-1 overflow-y-auto px-4 py-6 min-h-0" aria-live="polite">
            <div className="max-w-2xl mx-auto space-y-8">
              {messages.map((msg) =>
                msg.role === "user" ? (
                  /* User — right aligned, blue bubble */
                  <div key={msg.id} className="flex flex-col items-end gap-1">
                    <span className="text-[10px] font-bold tracking-[3px] uppercase text-muted-foreground">
                      You
                    </span>
                    <div className="bg-secondary text-secondary-foreground px-4 py-3 text-sm max-w-sm leading-relaxed">
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  /* Tommy — left aligned with avatar */
                  <div key={msg.id} className="flex gap-3 items-start">
                    <div className="relative w-10 h-12 shrink-0 overflow-hidden rounded-sm">
                      <Image
                        src="/tommyvance.png"
                        alt="Tommy Vance"
                        fill
                        sizes="40px"
                        className="object-cover object-top"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-[10px] font-bold tracking-[3px] uppercase text-primary">
                        Tommy Vance
                      </span>
                      <div className="border-t-2 border-primary mt-1 pt-3">
                        <div className="border border-border bg-card p-4 text-sm">
                          <p className="whitespace-pre-wrap leading-relaxed text-card-foreground">
                            {stripCitations(msg.content)}
                          </p>
                          {msg.citations && msg.citations.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 mt-3">
                              {msg.citations.map((c) => (
                                <CitationChip key={c.formatted} citation={c} />
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )
              )}

              {isLoading && (
                <div className="flex gap-3 items-start">
                  <div className="relative w-10 h-12 shrink-0 overflow-hidden rounded-sm">
                    <Image
                      src="/tommyvance.png"
                      alt="Tommy Vance"
                      fill
                      sizes="40px"
                      className="object-cover object-top"
                    />
                  </div>
                  <p className="text-sm text-muted-foreground animate-pulse self-center">
                    Tommy is thinking…
                  </p>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>

          {/* Bottom input bar */}
          <div className="shrink-0 border-t-4 border-foreground bg-background">
            <div className="max-w-2xl mx-auto">
              <QueryInput
                ref={inputRef}
                value={input}
                onChange={setInput}
                onSubmit={() => handleSubmit()}
                onKeyDown={handleKeyDown}
                isLoading={isLoading}
                inputLabel="Ask a follow-up question"
                submitLabel="Send follow-up question"
              />
            </div>
            <div className="border-t-2 border-primary" />
          </div>
        </>
      )}
    </section>
  );
}

const QueryInput = forwardRef<
  HTMLInputElement,
  {
    value: string;
    onChange: (v: string) => void;
    onSubmit: () => void;
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
    isLoading: boolean;
    inputLabel: string;
    submitLabel: string;
  }
>(function QueryInput(
  { value, onChange, onSubmit, onKeyDown, isLoading, inputLabel, submitLabel },
  ref
) {
  return (
    <div className="flex items-stretch">
      <input
        ref={ref}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask Tommy about the Friday Rock Show..."
        aria-label={inputLabel}
        className="flex-1 bg-background px-4 py-4 text-sm text-foreground placeholder:text-muted-foreground outline-none border border-border rounded-sm"
        disabled={isLoading}
      />
      <button
        onClick={onSubmit}
        disabled={isLoading || !value.trim()}
        aria-label={submitLabel}
        className="bg-primary text-primary-foreground px-6 text-[11px] font-black tracking-[2px] hover:bg-primary/90 transition-colors disabled:opacity-50 shrink-0"
      >
        {isLoading ? "…" : "AskTV"}
      </button>
    </div>
  );
});
