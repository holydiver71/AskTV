"use client";

import { useState, useRef, useEffect } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { CitationChip } from "@/components/citation-chip";
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const shouldRefocusInput = useRef(false);
  const hasMessages = messages.length > 0;

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

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <section className="flex flex-col flex-1 min-h-0" aria-label="Ask Tommy chat">
      {!hasMessages ? (
        /* ── Tommy hero — first-view ─────────────────────────── */
        <div className="flex flex-col flex-1 items-center justify-center px-4 py-12 gap-6 animate-hero-reveal">
          {/* Portrait — front and centre */}
          <div
            className="relative w-44 h-60 md:w-52 md:h-72 rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10 focus-visible:outline-none focus-visible:ring-[var(--focus-ring-width)] focus-visible:ring-ring/50"
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

          {/* Identity */}
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

          {/* Query box — directly beneath the image */}
          <div className="w-full max-w-xl space-y-3">
            <QueryInput
              ref={inputRef}
              value={input}
              onChange={setInput}
              onSubmit={() => handleSubmit()}
              onKeyDown={handleKeyDown}
              isLoading={isLoading}
              textareaLabel="Ask Tommy question"
              submitLabel="Submit question"
            />

            {/* Suggested prompts */}
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
          {/* Compact Tommy header */}
          <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-background/80 backdrop-blur sticky top-0 z-10 shrink-0">
            <div className="relative w-7 h-9 rounded overflow-hidden ring-1 ring-white/10 shrink-0">
              <Image
                src="/tommyvance.png"
                alt="Tommy Vance"
                fill
                sizes="28px"
                className="object-cover object-top"
              />
            </div>
            <div>
              <p className="text-sm font-semibold leading-none">Tommy Vance</p>
              <p className="text-xs text-muted-foreground leading-none mt-0.5">
                Friday Rock Show Archive
              </p>
            </div>
          </div>

          {/* Message list */}
          <div className="flex-1 overflow-y-auto px-4 py-6 min-h-0" aria-live="polite">
            <div className="max-w-2xl mx-auto space-y-6">
              {messages.map((msg) =>
                msg.role === "user" ? (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-sm bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm">
                      {msg.content}
                    </div>
                  </div>
                ) : (
                  <div key={msg.id} className="flex justify-start">
                    <div className="max-w-prose text-sm space-y-2">
                      <p className="whitespace-pre-wrap leading-relaxed">
                        {msg.content}
                      </p>
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {msg.citations.map((c) => (
                            <CitationChip key={c.formatted} citation={c} />
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              )}
              {isLoading && (
                <div className="flex justify-start">
                  <p className="text-sm text-muted-foreground animate-pulse">
                    Tommy is thinking…
                  </p>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* Bottom query input */}
          <div className="border-t border-border px-4 py-3 bg-background shrink-0">
            <div className="max-w-2xl mx-auto">
              <QueryInput
                ref={inputRef}
                value={input}
                onChange={setInput}
                onSubmit={() => handleSubmit()}
                onKeyDown={handleKeyDown}
                isLoading={isLoading}
                textareaLabel="Ask follow-up question"
                submitLabel="Send follow-up question"
              />
            </div>
          </div>
        </>
      )}
    </section>
  );
}

import { forwardRef } from "react";

const QueryInput = forwardRef<
  HTMLTextAreaElement,
  {
    value: string;
    onChange: (v: string) => void;
    onSubmit: () => void;
    onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
    isLoading: boolean;
    textareaLabel: string;
    submitLabel: string;
  }
>(function QueryInput(
  { value, onChange, onSubmit, onKeyDown, isLoading, textareaLabel, submitLabel },
  ref
) {
  return (
    <div className="flex gap-2 items-end">
      <Textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask Tommy anything about the Friday Rock Show…"
        aria-label={textareaLabel}
        className="resize-none min-h-[52px] max-h-40"
        rows={2}
        disabled={isLoading}
      />
      <Button
        onClick={onSubmit}
        disabled={isLoading}
        className="shrink-0 h-[52px] px-4"
        aria-label={submitLabel}
      >
          {isLoading ? "…" : "AskTV"}
      </Button>
    </div>
  );
});
