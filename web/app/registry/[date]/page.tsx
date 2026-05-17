import { getEpisode } from "@/lib/db/episodes";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { formatTimestamp } from "@/lib/utils/citations";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  return {
    title: `${date} — The Friday Rock Show Archive`,
  };
}

export default async function EpisodeDetailPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const episode = await getEpisode(date).catch(() => null);

  if (!episode) notFound();

  const displayDate = new Date(episode.date + "T00:00:00").toLocaleDateString(
    "en-GB",
    { weekday: "long", day: "numeric", month: "long", year: "numeric" }
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="space-y-1">
        <Link
          href="/registry"
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Registry
        </Link>
        <h1 className="text-3xl font-bold tracking-tight mt-2">{displayDate}</h1>
        <p className="font-mono text-xs text-muted-foreground">{episode.date}</p>
        {episode.url && (
          <a
            href={episode.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:underline inline-block"
          >
            Fandom Wiki ↗
          </a>
        )}
        {episode.comments && episode.comments.length > 0 && (
          <p className="text-sm text-muted-foreground pt-1">
            {episode.comments.join(" · ")}
          </p>
        )}
      </div>

      {/* Sessions */}
      {episode.sessions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Sessions ({episode.sessions.length})
          </h2>
          <ul className="space-y-1.5">
            {episode.sessions.map((s) => (
              <li key={s.id} className="text-sm flex gap-2 flex-wrap">
                <span className="font-semibold">{s.artist}</span>
                {s.details && (
                  <span className="text-muted-foreground">— {s.details}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Tracks */}
      {episode.tracks.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Track listing ({episode.tracks.length})
          </h2>
          <ul className="space-y-2">
            {episode.tracks.map((t, i) => (
              <li key={t.id} className="flex items-baseline gap-2 text-sm">
                <span className="font-mono text-xs text-muted-foreground w-5 text-right shrink-0">
                  {i + 1}.
                </span>
                <span className="font-medium">{t.artist}</span>
                <span className="text-muted-foreground flex-1">— {t.track}</span>
                {t.verified_timestamp != null && (
                  <Badge
                    variant="outline"
                    className="font-mono text-xs shrink-0 ml-auto"
                  >
                    {formatTimestamp(t.verified_timestamp)}
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Ask Tommy CTA */}
      <div className="border-t border-border pt-6">
        <Link
          href={`/chat?q=Tell me about the ${episode.date} broadcast`}
          className="text-sm text-primary hover:underline"
        >
          Ask Tommy about this episode →
        </Link>
      </div>
    </div>
  );
}
