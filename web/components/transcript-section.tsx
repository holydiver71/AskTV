"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { formatTimestamp } from "@/lib/utils/citations";

type Segment = {
  id: string;
  chunk_start: number;
  chunk_end: number;
  text: string;
};

export function TranscriptSection({ date }: { date: string }) {
  const [open, setOpen] = useState(false);
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState(false);

  async function handleToggle() {
    if (!open && segments === null && !fetchError) {
      setLoading(true);
      try {
        const res = await fetch(`/api/transcript/${date}`);
        if (!res.ok) throw new Error(String(res.status));
        const json = await res.json();
        setSegments(json.segments ?? []);
      } catch {
        setFetchError(true);
      } finally {
        setLoading(false);
      }
    }
    setOpen((v) => !v);
  }

  return (
    <div>
      <button
        onClick={handleToggle}
        className="w-full flex items-center gap-3.5 cursor-pointer group"
      >
        <h3 className="text-[11px] font-bold tracking-[3px] uppercase text-[#CC0000] whitespace-nowrap">
          Transcript
        </h3>
        <div className="flex-1 h-px bg-[#e0e0e0]" />
        <ChevronDown
          className={`w-4 h-4 text-[#888] shrink-0 transition-transform duration-200 ${
            open ? "rotate-0" : "-rotate-90"
          }`}
        />
      </button>

      {open && (
        <div className="mt-5">
          {loading && (
            <p className="text-xs text-[#888] py-4">Loading transcript…</p>
          )}
          {fetchError && (
            <p className="text-xs text-[#CC0000] py-4">
              Failed to load transcript.
            </p>
          )}
          {!loading && !fetchError && segments !== null && (
            segments.length === 0 ? (
              <p className="text-xs text-[#888] italic py-4">
                No transcript available for this episode.
              </p>
            ) : (
              <div className="space-y-5">
                {segments.map((seg) => (
                  <div key={seg.id} className="flex gap-5 items-baseline">
                    <span className="font-mono text-[10px] font-bold text-[#003087] shrink-0 w-16 text-right tabular-nums">
                      {formatTimestamp(seg.chunk_start)}
                    </span>
                    <p className="text-sm text-[#333] leading-relaxed flex-1">
                      {seg.text}
                    </p>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
