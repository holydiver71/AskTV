import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import type { Episode } from "@/lib/types/database";

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
          {episode.comments && episode.comments.length > 0 && (
            <p className="text-xs text-muted-foreground line-clamp-2">
              {episode.comments[0]}
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
