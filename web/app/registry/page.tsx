import { getEpisodes, getEpisodeYears } from "@/lib/db/episodes";
import { EpisodeCard } from "@/components/episode-card";
import { RegistryFilters } from "@/components/registry-filters";

export const metadata = {
  title: "The Music Vendor — The Friday Rock Show Archive",
};

export default async function RegistryPage({
  searchParams,
}: {
  searchParams: Promise<{ artist?: string; year?: string }>;
}) {
  const { artist, year } = await searchParams;
  const selectedYear = year?.match(/^\d{4}$/) ? year : "";

  let episodes: Awaited<ReturnType<typeof getEpisodes>> = [];
  let availableYears: string[] = [];
  let error: string | null = null;

  try {
    // Current dataset is small enough to fetch years and episodes together.
    [episodes, availableYears] = await Promise.all([
      getEpisodes({ artist, year: selectedYear, limit: 250 }),
      getEpisodeYears(),
    ]);
  } catch (err) {
    error = "Failed to load episodes. Please try again later.";
    console.error("[registry]", err);
  }

  // Show registry in ascending date order (oldest first)
  episodes = episodes.sort((a, b) => a.date.localeCompare(b.date));

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1
          className="font-black text-[#111] leading-[0.9]"
          style={{ fontSize: "clamp(2rem, 5vw, 3.5rem)", letterSpacing: "-2px" }}
        >
          The Music Vendor
        </h1>
      </div>

      <RegistryFilters
        artist={artist}
        year={selectedYear}
        availableYears={availableYears}
      />

      {/* Year / Count header (matches prototype layout) */}
      <div className="flex items-end justify-between border-b border-border pb-4">
        <div>
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight">
            {selectedYear || "All years"}
            {artist ? (
              <span className="text-2xl sm:text-3xl font-semibold text-muted-foreground ml-3">· filtered by "{artist}"</span>
            ) : null}
          </h2>
        </div>

        <div className="text-right">
          <div className="text-4xl sm:text-5xl font-extrabold text-amber-400 leading-none">{String(episodes.length).padStart(2, "0")}</div>
          <div className="uppercase text-xs tracking-widest text-muted-foreground">Episodes on record</div>
        </div>
      </div>

      {error ? (
        <p className="text-destructive text-sm">{error}</p>
      ) : episodes.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No episodes found
          {selectedYear ? ` in ${selectedYear}` : ""}
          {artist ? ` for artist "${artist}"` : ""}.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2">
          {episodes.map((ep, i) => (
            <EpisodeCard key={ep.id} episode={ep} index={i + 1} />
          ))}
        </div>
      
      )}
    </div>
  );
}
