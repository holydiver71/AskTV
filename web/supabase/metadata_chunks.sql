-- ============================================================
-- metadata_chunks table — embeddable documents derived from
-- tracks and sessions for hybrid RAG retrieval.
--
-- Run this once in the Supabase SQL Editor after the main
-- migrate_schema.sql migration has been applied.
-- Safe to re-run: all statements use IF NOT EXISTS / OR REPLACE
-- ============================================================

-- ------------------------------------------------------------
-- 1. Table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS metadata_chunks (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id   uuid        NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    source_type  text        NOT NULL CHECK (source_type IN ('track', 'session')),
    date         date        NOT NULL,
    chunk_start  float8,     -- verified_timestamp (seconds) for tracks; NULL for sessions
    chunk_end    float8,     -- reserved for future range use; NULL for metadata chunks
    text         text        NOT NULL,
    embedding    vector(512) -- NULL until vectorise_metadata.py runs
);

CREATE INDEX IF NOT EXISTS metadata_chunks_episode_id_idx
    ON metadata_chunks(episode_id);

-- HNSW index for fast approximate nearest-neighbour search
CREATE INDEX IF NOT EXISTS metadata_chunks_embedding_hnsw_idx
    ON metadata_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ------------------------------------------------------------
-- 2. Row-Level Security
-- ------------------------------------------------------------
ALTER TABLE metadata_chunks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "public_read_metadata_chunks" ON metadata_chunks;

CREATE POLICY "public_read_metadata_chunks"
    ON metadata_chunks FOR SELECT USING (true);
