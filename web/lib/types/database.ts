// TypeScript types mirroring the Supabase schema from scripts/migrate_schema.sql

export type Episode = {
  id: string;
  date: string;         // "YYYY-MM-DD"
  title: string;
  url: string | null;
  comments: string[] | null;
  episode_length_seconds?: number | null;
  session_artists?: string[];
};

export type Session = {
  id: string;
  episode_id: string;
  artist: string;
  details: string | null;
  position: number;
};

export type Track = {
  id: string;
  episode_id: string;
  artist: string;
  track: string;
  details: string | null;
  verified_timestamp: number | null; // seconds from start of broadcast
  position: number;
};

export type TranscriptSegment = {
  id: string;
  episode_id: string;
  chunk_start: number;
  chunk_end: number;
  text: string;
  // embedding: number[] — excluded; not selected in normal queries
};

export type EpisodeDetail = Episode & {
  sessions: Session[];
  tracks: Track[];
};

// Returned by the match_transcript_segments RPC function
export type SegmentMatch = {
  id: string;
  episode_id: string;
  chunk_start: number;
  chunk_end: number;
  text: string;
  date: string;         // joined from episodes
  similarity: number;
};

/** Source of a retrieved knowledge chunk. */
export type SourceType = "transcript" | "track" | "session";

/**
 * Unified retrieval match returned by the match_hybrid RPC function.
 * chunk_start / chunk_end are null for metadata rows that have no timestamp.
 */
export type UnifiedMatch = {
  id: string;
  episode_id: string;
  source_type: SourceType;
  chunk_start: number | null;
  chunk_end: number | null;
  text: string;
  date: string;
  similarity: number;
};
