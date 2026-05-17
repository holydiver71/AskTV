import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { Citation } from "@/lib/utils/citations";

export function CitationChip({ citation }: { citation: Citation }) {
  return (
    <Link
      href={`/registry/${citation.date}`}
      title={citation.text || undefined}
      aria-label={`Open registry for citation ${citation.formatted}`}
    >
      <Badge
        variant="outline"
        className="font-mono text-xs cursor-pointer hover:bg-muted transition-colors animate-citation-in"
      >
        {citation.formatted}
      </Badge>
    </Link>
  );
}
