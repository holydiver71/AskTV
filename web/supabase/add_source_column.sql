-- Add "source" column to transcript_segments.
-- Values: 'TV' (Tommy Vance), 'other' (guest/soundbite), NULL (music / not yet tagged).
ALTER TABLE transcript_segments
  ADD COLUMN IF NOT EXISTS source TEXT;

-- Optional index to speed up queries that filter by source.
CREATE INDEX IF NOT EXISTS idx_transcript_segments_source
  ON transcript_segments (source)
  WHERE source IS NOT NULL;