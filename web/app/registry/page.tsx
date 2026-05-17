import { getEpisodes } from "@/lib/db/episodes";
import { EpisodeCard } from "@/components/episode-card";
import { RegistryFilters } from "@/components/registry-filters";

export const metadata = {
  title: "Episode Registry — The Friday Rock Show Archive",
};

export default async function RegistryPage({
  searchParams,
}: {
  searchParams: Promise<{ artist?: string }>;
}) {
  const { artist } = await searchParams;

  let episodes: Awaited<ReturnType<typeof getEpisodes>> = [];
  let error: string | null = null;

  try {
    // Load all 1980 episodes (49 total) — no pagination needed yet.
    episodes = await getEpisodes({ artist, limit: 49 });
  } catch (err) {
    error = "Failed to load episodes. Please try again later.";
    console.error("[registry]", err);
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Episode Registry</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          1980 broadcasts
          {artist ? ` · filtered by "${artist}"` : ""} ·{" "}
          {episodes.length} episode{episodes.length !== 1 ? "s" : ""}
        </p>
      </div>

      <RegistryFilters artist={artist} />

      {error ? (
        <p className="text-destructive text-sm">{error}</p>
      ) : episodes.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No episodes found{artist ? ` for artist "${artist}"` : ""}.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {episodes.map((ep) => (
            <EpisodeCard key={ep.id} episode={ep} />
          ))}
        </div>
      )}
    </div>
  );
}
