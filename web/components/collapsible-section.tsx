"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

export function CollapsibleSection({
  title,
  count,
  children,
  defaultOpen = true,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3.5 mb-5 cursor-pointer group"
      >
        <h3 className="text-[11px] font-bold tracking-[3px] uppercase text-[#CC0000] whitespace-nowrap">
          {title}
        </h3>
        <div className="flex-1 h-px bg-[#e0e0e0]" />
        <span className="bg-[#003087] text-white text-[13px] font-black tracking-normal px-3 py-1 min-w-[28px] text-center">
          {count}
        </span>
        <ChevronDown
          className={`w-4 h-4 text-[#888] shrink-0 transition-transform duration-200 ${
            open ? "rotate-0" : "-rotate-90"
          }`}
        />
      </button>
      {open && children}
    </div>
  );
}
