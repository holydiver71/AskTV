-- ============================================================
-- Friday Rock Show Archive — Supabase Schema Migration
-- Run once in the Supabase SQL Editor (Project → SQL Editor)
-- Safe to re-run: all statements use IF NOT EXISTS / OR REPLACE / DROP IF EXISTS
-- ============================================================

-- Require pgvector (enable via Extensions if not already done)
CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- 1. episodes
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS episodes (
    id      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    date    date        NOT NULL UNIQUE,
    title   text        NOT NULL,
    url     text,
    comments text[]     NOT NULL DEFAULT '{}'
);

-- ------------------------------------------------------------
-- 2. sessions  (live/studio session features within an episode)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id  uuid        NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    artist      text        NOT NULL,
    details     text,
    position    smallint    NOT NULL    -- list order preserved from source JSON
);

CREATE INDEX IF NOT EXISTS sessions_episode_id_idx ON sessions(episode_id);

-- ------------------------------------------------------------
-- 3. tracks  (track listing per episode)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tracks (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id          uuid        NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    artist              text        NOT NULL,
    track               text        NOT NULL,
    details             text,
    verified_timestamp  float8,     -- seconds from start of MP3, NULL if unverified
    position            smallint    NOT NULL    -- list order preserved from source JSON
);

CREATE INDEX IF NOT EXISTS tracks_episode_id_idx ON tracks(episode_id);
CREATE INDEX IF NOT EXISTS tracks_artist_idx     ON tracks(lower(artist));

-- ------------------------------------------------------------
-- 4. transcript_segments  (Whisper chunks + embeddings)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcript_segments (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id  uuid        NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    chunk_start float8      NOT NULL,   -- seconds from start of MP3
    chunk_end   float8      NOT NULL,
    text        text        NOT NULL,
    embedding   vector(512)             -- NULL until vectorise_transcripts.py runs
);

CREATE INDEX IF NOT EXISTS transcript_segments_episode_id_idx
    ON transcript_segments(episode_id);

-- HNSW index for fast approximate nearest-neighbour search
-- m=16, ef_construction=64 are good defaults for this dataset size
CREATE INDEX IF NOT EXISTS transcript_segments_embedding_hnsw_idx
    ON transcript_segments
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ------------------------------------------------------------
-- 5. Row-Level Security
-- Anon key: read-only on episodes/sessions/tracks/transcript_segments
-- Service role: full access (bypasses RLS — used by upload & vectorise scripts)
-- ------------------------------------------------------------
ALTER TABLE episodes             ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions             ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracks               ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcript_segments  ENABLE ROW LEVEL SECURITY;

-- Public read access for the frontend (anon key)
-- DROP first so this block is safe to re-run
DROP POLICY IF EXISTS "public_read_episodes"            ON episodes;
DROP POLICY IF EXISTS "public_read_sessions"            ON sessions;
DROP POLICY IF EXISTS "public_read_tracks"              ON tracks;
DROP POLICY IF EXISTS "public_read_transcript_segments" ON transcript_segments;

CREATE POLICY "public_read_episodes"
    ON episodes FOR SELECT USING (true);

CREATE POLICY "public_read_sessions"
    ON sessions FOR SELECT USING (true);

CREATE POLICY "public_read_tracks"
    ON tracks FOR SELECT USING (true);

CREATE POLICY "public_read_transcript_segments"
    ON transcript_segments FOR SELECT USING (true);

-- ------------------------------------------------------------
-- 6. Helper: vector similarity search function
-- Call from the Phase 3 API: match_transcript_segments(query_embedding, 5)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_transcript_segments(
    query_embedding vector(512),
    match_count     int DEFAULT 5
)
RETURNS TABLE (
    episode_date    date,
    chunk_start     float8,
    chunk_end       float8,
    text            text,
    similarity      float
)
LANGUAGE sql STABLE AS $$
    SELECT
        e.date          AS episode_date,
        ts.chunk_start,
        ts.chunk_end,
        ts.text,
        1 - (ts.embedding <=> query_embedding) AS similarity
    FROM transcript_segments ts
    JOIN episodes e ON e.id = ts.episode_id
    WHERE ts.embedding IS NOT NULL
    ORDER BY ts.embedding <=> query_embedding
    LIMIT match_count;
$$;
