-- ============================================================
-- match_hybrid — unified retrieval over transcript_segments and
-- metadata_chunks, combining vector similarity with full-text search.
--
-- Two retrieval legs:
--   1. Vector (cosine): both transcript_segments and metadata_chunks
--   2. Full-text (PostgreSQL FTS): transcript_segments only,
--      activated when query_text is provided.
--
-- Duplicates (same chunk found by both legs) are collapsed to the
-- highest-scoring row before the final LIMIT is applied.
--
-- Run this in the Supabase SQL Editor after:
--   1. metadata_chunks.sql  (creates the metadata_chunks table)
--   2. vectorise_metadata.py has populated embeddings
--
-- Re-running is safe (DROP + CREATE replaces the old 3-param version).
-- ============================================================

-- Drop the previous 3-parameter signature so OR REPLACE can upgrade cleanly.
DROP FUNCTION IF EXISTS match_hybrid(vector(512), int, float8);

CREATE OR REPLACE FUNCTION match_hybrid(
    query_embedding  vector(512),
    query_text       text    DEFAULT '',
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
WITH combined AS (

    -- Leg 1a: vector search — transcript_segments
    SELECT
        ts.id,
        ts.episode_id,
        'transcript'::text                          AS source_type,
        ts.chunk_start,
        ts.chunk_end,
        ts.text,
        e.date,
        1 - (ts.embedding <=> query_embedding)      AS similarity
    FROM  transcript_segments ts
    JOIN  episodes e ON e.id = ts.episode_id
    WHERE ts.embedding IS NOT NULL
      AND 1 - (ts.embedding <=> query_embedding) > match_threshold

    UNION ALL

    -- Leg 1b: vector search — metadata_chunks
    SELECT
        mc.id,
        mc.episode_id,
        mc.source_type,
        mc.chunk_start,
        mc.chunk_end,
        mc.text,
        mc.date,
        1 - (mc.embedding <=> query_embedding)      AS similarity
    FROM  metadata_chunks mc
    WHERE mc.embedding IS NOT NULL
      AND 1 - (mc.embedding <=> query_embedding) > match_threshold

    UNION ALL

    -- Leg 2: full-text search — transcript_segments
    -- Activated only when query_text is non-empty.
    -- Similarity is fixed at (match_threshold + 0.01) so FTS matches are
    -- included but ranked below strong vector hits.
    SELECT
        ts.id,
        ts.episode_id,
        'transcript'::text                          AS source_type,
        ts.chunk_start,
        ts.chunk_end,
        ts.text,
        e.date,
        (match_threshold + 0.01)                    AS similarity
    FROM  transcript_segments ts
    JOIN  episodes e ON e.id = ts.episode_id
    WHERE length(query_text) >= 3
      AND to_tsvector('english', ts.text)
              @@ websearch_to_tsquery('english', query_text)

),

-- Collapse duplicates: keep the highest similarity score per chunk id.
deduped AS (
    SELECT DISTINCT ON (id)
        id, episode_id, source_type, chunk_start, chunk_end, text, date, similarity
    FROM  combined
    ORDER BY id, similarity DESC
)

SELECT id, episode_id, source_type, chunk_start, chunk_end, text, date, similarity
FROM   deduped
ORDER  BY similarity DESC
LIMIT  match_count;
$$;
