-- ============================================================
-- match_hybrid — unified vector similarity search over both
-- transcript_segments and metadata_chunks.
--
-- Returns up to match_count rows from a UNION of both tables,
-- ordered by similarity (cosine distance), filtered by threshold.
--
-- Run this in the Supabase SQL Editor after:
--   1. metadata_chunks.sql  (creates the metadata_chunks table)
--   2. vectorise_metadata.py has populated embeddings
-- ============================================================

CREATE OR REPLACE FUNCTION match_hybrid(
    query_embedding  vector(512),
    match_count      int     DEFAULT 12,
    match_threshold  float8  DEFAULT 0.35
)
RETURNS TABLE (
    id           uuid,
    episode_id   uuid,
    source_type  text,
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
        'transcript'::text          AS source_type,
        ts.chunk_start,
        ts.chunk_end,
        ts.text,
        e.date,
        1 - (ts.embedding <=> query_embedding) AS similarity
    FROM  transcript_segments ts
    JOIN  episodes e ON e.id = ts.episode_id
    WHERE ts.embedding IS NOT NULL
      AND 1 - (ts.embedding <=> query_embedding) > match_threshold

    UNION ALL

    SELECT
        mc.id,
        mc.episode_id,
        mc.source_type,
        mc.chunk_start,
        mc.chunk_end,
        mc.text,
        mc.date,
        1 - (mc.embedding <=> query_embedding) AS similarity
    FROM  metadata_chunks mc
    WHERE mc.embedding IS NOT NULL
      AND 1 - (mc.embedding <=> query_embedding) > match_threshold

    ORDER BY similarity DESC
    LIMIT match_count;
$$;
