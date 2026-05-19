import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import type { Episode } from "@/lib/types/database";

function formatEpisodeLength(seconds: number | null | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds <= 0) {
    return "unknown";
  }

  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function EpisodeCard({
  episode,
  index,
}: {
  episode: Episode & { track_count?: number };
  index?: number;
}) {
  const displayDate = new Date(episode.date + "T00:00:00").toLocaleDateString(
    "en-GB",
    { day: "numeric", month: "long", year: "numeric" }
  );

  const weekday = new Date(episode.date + "T00:00:00").toLocaleDateString(
    "en-GB",
    { weekday: "long" }
  );

  const idxStr = index != null ? String(index).padStart(2, "0") : "";
  const scale = idxStr.length >= 3 ? 0.72 : idxStr.length === 2 ? 0.92 : 1;

  return (
    <Link href={`/registry/${episode.date}`}>
      <Card className="group relative h-full transition-colors duration-200 cursor-pointer overflow-hidden bg-background hover:bg-[#003087]/5 border-l-[3px] border-l-[#003087]">
        {index != null && (
          <div
            className="pointer-events-none absolute top-1 right-3 text-5xl sm:text-6xl font-extrabold text-muted-foreground/10 leading-none transition-colors group-hover:text-[#CC0000]"
            style={{ transform: `scale(${scale})`, transformOrigin: "right top" }}
          >
            {idxStr}
          </div>
        )}

        <CardContent className="py-6 px-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-start">
            <div>
              <p className="text-2xl font-bold leading-tight">{displayDate}</p>
              <p className="font-mono text-xs text-muted-foreground mt-1">{weekday}</p>
            </div>

            <div className="text-sm text-muted-foreground">
              <div className="flex gap-6 items-center mt-1">
                <div>
                  <div className="font-semibold text-2xl text-foreground">{episode.track_count ?? "—"}</div>
                  <div className="uppercase text-xs tracking-wider text-muted-foreground">tracks</div>
                </div>
                <div>
                  <div className="font-semibold text-2xl text-foreground">{(episode.session_artists ?? []).length}</div>
                  <div className="uppercase text-xs tracking-wider text-muted-foreground">sessions</div>
                </div>
              </div>

              {(episode.title || episode.comments) && (
                <p className="mt-4 text-sm text-muted-foreground line-clamp-3">
                  {episode.comments && episode.comments.length > 0
                    ? episode.comments.join(" — ")
                    : episode.title}
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
