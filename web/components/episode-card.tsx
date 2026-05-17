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

export function EpisodeCard({ episode }: { episode: Episode }) {
  const displayDate = new Date(episode.date + "T00:00:00").toLocaleDateString(
    "en-GB",
    { day: "numeric", month: "long", year: "numeric" }
  );

  return (
    <Link href={`/registry/${episode.date}`}>
      <Card className="h-full hover:bg-muted/40 transition-colors cursor-pointer">
        <CardContent className="py-4 px-4 space-y-1">
          <p className="font-mono text-xs text-muted-foreground">{episode.date}</p>
          <p className="font-medium text-sm">{displayDate}</p>
          <p className="text-xs text-muted-foreground">
            Episode length: {formatEpisodeLength(episode.episode_length_seconds)}
          </p>
          {episode.session_artists && episode.session_artists.length > 0 && (
            <p className="text-xs text-muted-foreground line-clamp-2">
              Sessions: {episode.session_artists.join(", ")}
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
