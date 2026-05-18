import { createSupabaseServer } from "@/lib/supabase/server";
import type { Episode, EpisodeDetail, Session, Track } from "@/lib/types/database";

export type { Episode, EpisodeDetail, Session, Track };

/** Fetch a paginated list of episodes, optionally filtered by artist name. */
export async function getEpisodes(opts?: {
  artist?: string;
  year?: string;
  limit?: number;
  offset?: number;
}): Promise<Episode[]> {
  const supabase = await createSupabaseServer();
  const limit = opts?.limit ?? 20;
  const offset = opts?.offset ?? 0;

  // If artist filter is active, resolve matching episode IDs via tracks/sessions.
  let episodeIds: string[] | null = null;
  if (opts?.artist?.trim()) {
    const term = `%${opts.artist.trim()}%`;
    const [{ data: trackHits }, { data: sessionHits }] = await Promise.all([
      supabase.from("tracks").select("episode_id").ilike("artist", term),
      supabase.from("sessions").select("episode_id").ilike("artist", term),
    ]);
    episodeIds = [
      ...new Set([
        ...(trackHits?.map((t) => t.episode_id) ?? []),
        ...(sessionHits?.map((s) => s.episode_id) ?? []),
      ]),
    ];
    if (episodeIds.length === 0) return [];
  }

  let query = supabase
    .from("episodes")
    .select("id, date, title, url, comments")
    .order("date", { ascending: false });

  if (opts?.year?.match(/^\d{4}$/)) {
    query = query
      .gte("date", `${opts.year}-01-01`)
      .lte("date", `${opts.year}-12-31`);
  }

  query = query.range(offset, offset + limit - 1);

  if (episodeIds) {
    query = query.in("id", episodeIds);
  }

  const { data, error } = await query;
  if (error) throw new Error(`getEpisodes: ${error.message}`);

  const episodes = (data as Episode[]) ?? [];
  if (episodes.length === 0) return episodes;

  const episodeRowIds = episodes.map((ep) => ep.id);
  const [
    { data: sessions },
    { data: transcriptSegments },
    { data: tracksRows },
  ] = await Promise.all([
    supabase
      .from("sessions")
      .select("episode_id, artist, position")
      .in("episode_id", episodeRowIds)
      .order("position"),
    supabase
      .from("transcript_segments")
      .select("episode_id, chunk_end")
      .in("episode_id", episodeRowIds),
    supabase
      .from("tracks")
      .select("episode_id")
      .in("episode_id", episodeRowIds),
  ]);

  const sessionArtistsByEpisode = new Map<string, string[]>();
  for (const s of sessions ?? []) {
    const artists = sessionArtistsByEpisode.get(s.episode_id) ?? [];
    if (!artists.includes(s.artist)) {
      artists.push(s.artist);
      sessionArtistsByEpisode.set(s.episode_id, artists);
    }
  }

  const maxChunkEndByEpisode = new Map<string, number>();
  for (const seg of transcriptSegments ?? []) {
    const current = maxChunkEndByEpisode.get(seg.episode_id) ?? 0;
    if (seg.chunk_end > current) {
      maxChunkEndByEpisode.set(seg.episode_id, seg.chunk_end);
    }
  }

  const trackCountByEpisode = new Map<string, number>();
  for (const t of tracksRows ?? []) {
    const current = trackCountByEpisode.get(t.episode_id) ?? 0;
    trackCountByEpisode.set(t.episode_id, current + 1);
  }

  return episodes.map((ep) => ({
    ...ep,
    episode_length_seconds: maxChunkEndByEpisode.get(ep.id) ?? null,
    session_artists: sessionArtistsByEpisode.get(ep.id) ?? [],
    track_count: trackCountByEpisode.get(ep.id) ?? 0,
  }));
}

/** Fetch available episode years for UI filters. */
export async function getEpisodeYears(): Promise<string[]> {
  const supabase = await createSupabaseServer();
  const { data, error } = await supabase
    .from("episodes")
    .select("date")
    .order("date", { ascending: false });

  if (error) throw new Error(`getEpisodeYears: ${error.message}`);

  return [
    ...new Set(
      (data ?? [])
        .map((row) => String(row.date).slice(0, 4))
        .filter((year) => /^\d{4}$/.test(year))
    ),
  ];
}

/** Fetch a single episode with its full sessions and track listing. */
export async function getEpisode(date: string): Promise<EpisodeDetail | null> {
  const supabase = await createSupabaseServer();

  const { data: episode, error } = await supabase
    .from("episodes")
    .select("id, date, title, url, comments")
    .eq("date", date)
    .single();

  if (error || !episode) return null;

  const [{ data: sessions }, { data: tracks }] = await Promise.all([
    supabase
      .from("sessions")
      .select("id, artist, details, position")
      .eq("episode_id", episode.id)
      .order("position"),
    supabase
      .from("tracks")
      .select("id, artist, track, details, verified_timestamp, position")
      .eq("episode_id", episode.id)
      .order("position"),
  ]);

  return {
    ...(episode as Episode),
    sessions: (sessions as Session[]) ?? [],
    tracks: (tracks as Track[]) ?? [],
  };
}
