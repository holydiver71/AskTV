"""
upload_episodes.py
------------------
Reads all FRS YYYY-MM-DD.json files under data/episodes/1980/ and upserts
relational rows into Supabase:

  episodes          — one row per episode
  sessions          — session features listed in each episode
  tracks            — track listing (with verified_timestamp where present)
  transcript_segments — ~60-second text windows (no embeddings yet)
  metadata_chunks   — embeddable text documents derived from tracks/sessions
                       (no embeddings yet; vectorise_metadata.py fills them)

Re-running is safe: episodes upsert on (date), child rows are deleted and
re-inserted for any episode that is re-processed.

Usage:
  python scripts/upload_episodes.py [--dir data/episodes/1980]

Logs to logs/upload_episodes.log
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CHUNK_WINDOW_SECONDS = 60       # group transcript segments into ~60-s windows
SKIP_TEXTS = {"[Music]", "[redacted address]"}   # never embed these
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_PATH = Path("logs/upload_episodes.log")
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def episode_date_from_path(path: Path) -> str | None:
    """Extract YYYY-MM-DD from filename like 'FRS 1980-01-04.json'."""
    m = DATE_RE.search(path.stem)
    return m.group(0) if m else None


def build_chunks(transcript: list[dict]) -> list[dict]:
    """
    Merge consecutive Whisper segments into ~60-second windows.
    Skips segments whose text (stripped) is in SKIP_TEXTS.
    Returns list of {chunk_start, chunk_end, text}.
    """
    chunks: list[dict] = []
    window_start: float | None = None
    window_end: float | None = None
    window_texts: list[str] = []

    def flush():
        if window_texts:
            chunks.append({
                "chunk_start": window_start,
                "chunk_end":   window_end,
                "text":        " ".join(window_texts).strip(),
            })

    for seg in transcript:
        raw_text = seg.get("text", "").strip()
        if not raw_text or raw_text in SKIP_TEXTS:
            continue

        seg_start = float(seg["start"])
        seg_end   = float(seg["end"])

        if window_start is None:
            window_start = seg_start

        # Start a new window when this segment would push us past the limit
        if window_end is not None and (seg_end - window_start) > CHUNK_WINDOW_SECONDS:
            flush()
            window_start = seg_start
            window_texts = []

        window_end = seg_end
        window_texts.append(raw_text)

    flush()
    return chunks


def build_track_chunk_text(ep_date: str, t: dict) -> str:
    """Build a searchable text document for a single track row."""
    artist  = t.get("artist") or ""
    track   = t.get("track")  or ""
    details = t.get("details") or ""
    ts      = t.get("verified_timestamp")

    parts = [f"{ep_date}."]
    if artist:
        parts.append(f"Artist: {artist}.")
    if track:
        parts.append(f"Track: {track}.")
    if details:
        parts.append(f"Details: {details}.")
    if ts is not None:
        parts.append(f"Verified timestamp: {ts}.")
    return " ".join(parts)


def build_session_chunk_text(ep_date: str, s: dict) -> str:
    """Build a searchable text document for a single session row."""
    artist  = s.get("artist")  or ""
    details = s.get("details") or ""

    parts = [f"{ep_date}."]
    if artist:
        parts.append(f"Session artist: {artist}.")
    if details:
        parts.append(f"Details: {details}.")
    return " ".join(parts)


def upsert_episode(sb: Client, ep_data: dict) -> str:
    """
    Upsert an episodes row. Returns the episode UUID.
    Supabase upserts on the UNIQUE constraint (date).
    """
    row = {
        "date":     ep_data["show"]["date"],
        "title":    ep_data["title"],
        "url":      ep_data.get("url") or "",
        "comments": ep_data["show"].get("comments") or [],
    }
    result = (
        sb.table("episodes")
          .upsert(row, on_conflict="date")
          .execute()
    )
    return result.data[0]["id"]


def replace_children(sb: Client, episode_id: str, ep_data: dict) -> dict:
    """
    Delete and re-insert sessions, tracks, transcript_segments, and
    metadata_chunks for this episode. Deletion cascades are defined in the
    schema, but we do explicit deletes here so the function is self-contained.
    Returns counts {sessions, tracks, segments, metadata_chunks}.
    """
    # -- sessions ----------------------------------------------------------
    sb.table("sessions").delete().eq("episode_id", episode_id).execute()
    session_rows = [
        {
            "episode_id": episode_id,
            "artist":     s["artist"],
            "details":    s.get("details"),
            "position":   i,
        }
        for i, s in enumerate(ep_data.get("sessions") or [])
    ]
    if session_rows:
        sb.table("sessions").insert(session_rows).execute()

    # -- tracks ------------------------------------------------------------
    sb.table("tracks").delete().eq("episode_id", episode_id).execute()
    track_rows = []
    for i, t in enumerate(ep_data.get("track_listing") or []):
        artist = t.get("artist") or ""
        track  = t.get("track")  or ""
        if not track:
            continue
        track_rows.append({
            "episode_id":         episode_id,
            "artist":             artist,
            "track":              track,
            "details":            t.get("details"),
            "verified_timestamp": t.get("verified_timestamp"),
            "position":           i,
        })
    if track_rows:
        sb.table("tracks").insert(track_rows).execute()

    # -- transcript_segments -----------------------------------------------
    sb.table("transcript_segments").delete().eq("episode_id", episode_id).execute()
    chunks = build_chunks(ep_data.get("transcript") or [])
    segment_rows = [
        {
            "episode_id":  episode_id,
            "chunk_start": c["chunk_start"],
            "chunk_end":   c["chunk_end"],
            "text":        c["text"],
            # embedding left NULL — vectorise_transcripts.py fills this later
        }
        for c in chunks
    ]
    if segment_rows:
        # Insert in batches of 500 to avoid request-size limits
        batch = 500
        for start in range(0, len(segment_rows), batch):
            sb.table("transcript_segments").insert(
                segment_rows[start : start + batch]
            ).execute()

    # -- metadata_chunks (tracks + sessions) --------------------------------
    ep_date = ep_data["show"]["date"]
    sb.table("metadata_chunks").delete().eq("episode_id", episode_id).execute()
    chunk_rows: list[dict] = []

    for t in ep_data.get("track_listing") or []:
        track = t.get("track") or ""
        if not track:
            continue
        chunk_rows.append({
            "episode_id":  episode_id,
            "source_type": "track",
            "date":        ep_date,
            "chunk_start": t.get("verified_timestamp"),
            "chunk_end":   None,
            "text":        build_track_chunk_text(ep_date, t),
        })

    for s in ep_data.get("sessions") or []:
        chunk_rows.append({
            "episode_id":  episode_id,
            "source_type": "session",
            "date":        ep_date,
            "chunk_start": None,
            "chunk_end":   None,
            "text":        build_session_chunk_text(ep_date, s),
        })

    if chunk_rows:
        sb.table("metadata_chunks").insert(chunk_rows).execute()

    return {
        "sessions":       len(session_rows),
        "tracks":         len(track_rows),
        "segments":       len(segment_rows),
        "metadata_chunks": len(chunk_rows),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(episodes_dir: Path) -> None:
    load_dotenv()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        log.error("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        sys.exit(1)

    sb: Client = create_client(url, key)
    log.info("Connected to Supabase: %s", url)

    json_files = sorted(episodes_dir.glob("FRS *.json"))
    if not json_files:
        log.error("No FRS *.json files found in %s", episodes_dir)
        sys.exit(1)

    total = {"episodes": 0, "sessions": 0, "tracks": 0, "segments": 0, "metadata_chunks": 0}
    errors: list[str] = []

    for path in json_files:
        ep_date = episode_date_from_path(path)
        if not ep_date:
            log.warning("Cannot parse date from %s — skipping", path.name)
            continue

        try:
            with open(path, encoding="utf-8") as f:
                ep_data = json.load(f)

            episode_id = upsert_episode(sb, ep_data)
            counts = replace_children(sb, episode_id, ep_data)

            log.info(
                "%s  →  ep:%s  sessions:%d  tracks:%d  segments:%d  meta:%d",
                ep_date,
                episode_id[:8],
                counts["sessions"],
                counts["tracks"],
                counts["segments"],
                counts["metadata_chunks"],
            )

            total["episodes"] += 1
            total["sessions"] += counts["sessions"]
            total["tracks"]   += counts["tracks"]
            total["segments"] += counts["segments"]
            total["metadata_chunks"] += counts["metadata_chunks"]

        except Exception as exc:
            log.error("FAILED %s: %s", path.name, exc)
            errors.append(f"{path.name}: {exc}")

    log.info(
        "Done. episodes=%d  sessions=%d  tracks=%d  segments=%d  meta=%d",
        total["episodes"], total["sessions"], total["tracks"],
        total["segments"], total["metadata_chunks"],
    )
    if errors:
        log.warning("%d file(s) failed — see errors above", len(errors))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload FRS episodes to Supabase")
    parser.add_argument(
        "--dir",
        default="data/episodes/1980",
        help="Directory containing FRS *.json files (default: data/episodes/1980)",
    )
    args = parser.parse_args()
    main(Path(args.dir))
