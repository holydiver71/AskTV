-- Run this once in the Supabase SQL Editor after Phase 2 vectorisation is complete.
-- It exposes a pgvector similarity search as an RPC call for the Next.js API route.

CREATE OR REPLACE FUNCTION match_transcript_segments(
  query_embedding  vector(512),
  match_count      int     DEFAULT 8,
  match_threshold  float8  DEFAULT 0.45
)
RETURNS TABLE (
  id           uuid,
  episode_id   uuid,
  chunk_start  float8,
  chunk_end    float8,
  text         text,
  date         date,
  similarity   float8
)
LANGUAGE sql STABLE
AS $$
  SELECT
    ts.id,
    ts.episode_id,
    ts.chunk_start,
    ts.chunk_end,
    ts.text,
    e.date,
    1 - (ts.embedding <=> query_embedding) AS similarity
  FROM transcript_segments ts
  JOIN episodes e ON e.id = ts.episode_id
  WHERE 1 - (ts.embedding <=> query_embedding) > match_threshold
  ORDER BY ts.embedding <=> query_embedding
  LIMIT match_count;
$$;
