#!/usr/bin/env python3
"""Phase 1B — Shazam Music Fingerprinting for 1980 episodes.

Probes each 1980 MP3 every 180 seconds with a 15-second audio slice,
identifies tracks via ShazamIO, fuzzy-matches against track_listing entries,
and writes verified_timestamp (seconds float) to matched entries.

Run from the workspace root:
    python scripts/shazam_1980.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

from rapidfuzz import fuzz
from shazamio import Shazam


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AUDIO_DIR = Path(
    "/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/128kbps/1980/"
)
JSON_DIR = Path("data/episodes/1980/")
LOG_DIR = Path("logs/")
LOG_FILE = LOG_DIR / "shazam.log"

PROBE_INTERVAL = 180          # seconds between probe start points
PROBE_DURATION = 15           # seconds per probe slice
MATCH_THRESHOLD = 80          # rapidfuzz token_sort_ratio minimum for Shazam LP matches
SESSION_ARTIST_THRESHOLD = 75 # rapidfuzz partial_ratio minimum for transcript artist search
TRACK_TITLE_THRESHOLD = 80    # rapidfuzz partial_ratio minimum for transcript track-title search
SESSION_SEARCH_MIN_OFFSET = 120.0  # skip transcript before this offset (avoids opening preview)
PROBE_DELAY = 1.5             # seconds sleep between API calls (rate limiting)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def extract_probe(mp3_path: Path, offset_s: int, duration_s: int) -> bytes:
    """Extract a WAV audio slice from an MP3 via ffmpeg, returning raw bytes."""
    cmd = [
        "ffmpeg",
        "-ss", str(offset_s),
        "-t", str(duration_s),
        "-i", str(mp3_path),
        "-f", "wav",
        "-ac", "1",
        "-ar", "16000",
        "pipe:1",
        "-loglevel", "error",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}): {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def find_best_match(
    shazam_title: str,
    shazam_artist: str,
    track_listing: list,
) -> int | None:
    """Return the index of the best matching track_listing entry, or None."""
    query = f"{shazam_artist} {shazam_title}".lower()
    best_score = -1
    best_idx = None

    for idx, entry in enumerate(track_listing):
        # Skip entries already stamped — first match wins
        if "verified_timestamp" in entry:
            continue

        candidate = f"{entry.get('artist', '')} {entry.get('track', '')}".lower()
        score = fuzz.token_sort_ratio(query, candidate)
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_score >= MATCH_THRESHOLD:
        return best_idx
    return None


def stamp_unmatched_lp_from_transcript(
    track_listing: list,
    transcript: list,
    date: str,
) -> int:
    """Fallback: stamp LP tracks that Shazam couldn't match by searching for the
    track title in Tommy Vance's spoken introductions.

    Searches each unstamped non-session entry's track title against transcript
    segments using partial_ratio (most robust for short title substrings).
    Assigns the earliest matching segment's start time.

    Returns count of newly stamped tracks.
    """
    n_stamped = 0
    for entry in track_listing:
        if "verified_timestamp" in entry:
            continue
        if "session" in (entry.get("details") or "").lower():
            continue

        title = (entry.get("track") or "").lower()
        if not title:
            continue

        best_start: float | None = None
        best_score = -1

        for seg in transcript:
            text = (seg.get("text") or "").lower()
            score = fuzz.partial_ratio(title, text)
            if score >= TRACK_TITLE_THRESHOLD:
                start = seg.get("start")
                if start is not None and (best_start is None or start < best_start):
                    best_start = start
                    best_score = score

        display = f"{entry.get('artist')} \u2013 {entry.get('track')}"
        if best_start is not None:
            entry["verified_timestamp"] = float(best_start)
            n_stamped += 1
            log.info(
                f"[{date}] \u2713 LP transcript fallback: {display} @ {best_start:.1f}s "
                f"(transcript score {best_score:.0f})"
            )
        else:
            log.info(f"[{date}] UNMATCHED LP (no transcript hit): {display}")

    return n_stamped


def stamp_sessions_from_transcript(
    track_listing: list,
    transcript: list,
    date: str,
) -> int:
    """Assign verified_timestamp to session tracks via artist-name search in the transcript.

    Groups unstamped session tracks by (artist, details). For each group, finds
    the earliest transcript segment where the artist name appears (partial_ratio)
    and stamps the first track in that group.

    Note: Tommy sometimes back-announces (name spoken AFTER playing), so the
    timestamp may occasionally follow the music rather than precede it. These
    cases are visible in the log score.

    Returns count of newly stamped session tracks (one per unique session group).
    """
    from collections import defaultdict

    # Build full groups (all tracks per session, stamped or not)
    all_groups: dict[tuple, list[int]] = defaultdict(list)
    for idx, entry in enumerate(track_listing):
        details = (entry.get("details") or "").lower()
        if "session" not in details:
            continue
        artist = (entry.get("artist") or "").lower()
        all_groups[(artist, details)].append(idx)

    if not all_groups:
        return 0

    n_stamped = 0
    for (artist, _details), indices in all_groups.items():
        if not artist:
            continue
        # Skip the whole group if ANY member is already stamped
        if any("verified_timestamp" in track_listing[i] for i in indices):
            continue
        # Only consider the truly unstamped indices for the first-track selection
        unstamped = [i for i in indices if "verified_timestamp" not in track_listing[i]]
        if not unstamped:
            continue

        best_start: float | None = None
        best_score = -1

        for seg in transcript:
            start = seg.get("start")
            if start is None or start < SESSION_SEARCH_MIN_OFFSET:
                continue  # skip opening preview/credits where Tommy lists tonight's artists
            text = (seg.get("text") or "").lower()
            score = fuzz.partial_ratio(artist, text)
            if score >= SESSION_ARTIST_THRESHOLD:
                if best_start is None or start < best_start:
                    best_start = start
                    best_score = score

        display_artist = track_listing[unstamped[0]].get("artist", artist)
        if best_start is not None:
            track_listing[unstamped[0]]["verified_timestamp"] = float(best_start)
            n_stamped += 1
            log.info(
                f"[{date}] \u2713 Session intro: {display_artist} @ {best_start:.1f}s "
                f"(transcript score {best_score:.0f})"
            )
        else:
            log.info(f"[{date}] Session artist not found in transcript: {display_artist}")

    return n_stamped


# ---------------------------------------------------------------------------
# Async episode processor
# ---------------------------------------------------------------------------

async def process_episode(
    mp3_path: Path,
    json_path: Path,
    shazam: Shazam,
    date: str,
) -> None:
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    track_listing = data.get("track_listing", [])
    transcript = data.get("transcript", [])

    if not transcript:
        log.warning(f"[{date}] No transcript found — skipping (run transcription first)")
        return

    audio_duration = transcript[-1]["end"]

    # Count what needs stamping
    unstamped = [e for e in track_listing if "verified_timestamp" not in e]

    # Idempotency gate — skip when fully stamped
    if not unstamped:
        log.info(f"[{date}] Skipping — fully stamped")
        return

    n_matched = 0

    # Run Shazam probing for all unstamped tracks (LP and session)
    if unstamped:
        for offset in range(0, int(audio_duration), PROBE_INTERVAL):
            try:
                audio_bytes = extract_probe(mp3_path, offset, PROBE_DURATION)
            except RuntimeError as exc:
                log.error(f"[{date}] ffmpeg error at {offset}s: {exc}")
                await asyncio.sleep(PROBE_DELAY)
                continue

            try:
                result = await shazam.recognize(audio_bytes)
            except Exception as exc:
                log.warning(f"[{date}] Shazam error at {offset}s: {exc}")
                await asyncio.sleep(PROBE_DELAY)
                continue

            track_info = result.get("track")
            if not track_info:
                await asyncio.sleep(PROBE_DELAY)
                continue

            title = track_info.get("title", "")
            artist = track_info.get("subtitle", "")

            idx = find_best_match(title, artist, track_listing)
            if idx is not None:
                track_listing[idx]["verified_timestamp"] = float(offset)
                n_matched += 1
                log.info(f"[{date}] \u2713 Matched: {artist} \u2013 {title} @ {offset}s")

            await asyncio.sleep(PROBE_DELAY)

    # Transcript fallback for LP tracks Shazam couldn't match
    n_lp_transcript = stamp_unmatched_lp_from_transcript(track_listing, transcript, date)

    # Stamp session tracks using artist-name search in the transcript
    n_session_stamped = stamp_sessions_from_transcript(track_listing, transcript, date)

    # Collect any remaining unmatched LP tracks (neither Shazam nor transcript found them)
    unmatched_lp = [
        e for e in track_listing
        if "verified_timestamp" not in e
        and "session" not in (e.get("details") or "").lower()
    ]

    summary_parts = [f"{n_matched} track(s) via Shazam"]
    if n_lp_transcript:
        summary_parts.append(f"{n_lp_transcript} LP track(s) via transcript fallback")
    if n_session_stamped:
        summary_parts.append(f"{n_session_stamped} session track(s) via transcript fallback")
    if unmatched_lp:
        summary_parts.append(f"{len(unmatched_lp)} LP track(s) still unmatched")
    # Warn only if an entire session group has zero timestamps (intro completely missed)
    from collections import defaultdict as _dd
    _sg: dict = _dd(list)
    for _e in track_listing:
        _det = (_e.get("details") or "").lower()
        if "session" in _det:
            _sg[(_e.get("artist") or "").lower(), _det].append(_e)
    _missed_groups = [k for k, v in _sg.items() if not any("verified_timestamp" in e for e in v)]
    if _missed_groups:
        summary_parts.append(
            f"WARNING: {len(_missed_groups)} session group(s) with no intro timestamp found"
        )

    # Atomic write-back once, after all probes
    data["track_listing"] = track_listing
    _atomic_write(json_path, data)
    log.info(f"[{date}] Done \u2014 {', '.join(summary_parts)}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main(single_mp3: Path | None = None) -> None:
    if single_mp3 is not None:
        mp3_files = [single_mp3]
    else:
        mp3_files = sorted(AUDIO_DIR.glob("*.mp3"))

    if not mp3_files:
        log.error(f"No MP3 files found in {AUDIO_DIR}")
        return

    episodes: list[tuple[str, Path, Path]] = []
    for mp3_path in mp3_files:
        match = re.search(r"\d{4}-\d{2}-\d{2}", mp3_path.name)
        if not match:
            log.warning(f"Could not extract date from {mp3_path.name} — skipping")
            continue
        date = match.group()
        json_path = JSON_DIR / f"FRS {date}.json"
        if not json_path.exists():
            log.warning(f"[{date}] JSON not found: {json_path} — skipping")
            continue
        episodes.append((date, mp3_path, json_path))

    total = len(episodes)
    log.info(f"Found {total} episode(s) to process")

    shazam = Shazam()
    interrupted = False

    for n, (date, mp3_path, json_path) in enumerate(episodes, start=1):
        print(f"[{n}/{total}] Processing {date}…")
        try:
            await process_episode(mp3_path, json_path, shazam, date)
        except KeyboardInterrupt:
            print("\nInterrupt received — stopping after current episode.")
            interrupted = True
            break
        except Exception as exc:
            log.error(f"[{date}] Unexpected error: {exc}")

        if interrupted:
            break

    log.info("Run complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shazam fingerprinting for FRS episodes")
    parser.add_argument(
        "--mp3",
        type=Path,
        default=None,
        metavar="FILE",
        help="Process a single MP3 file instead of the full 1980 directory",
    )
    args = parser.parse_args()

    if args.mp3 is not None and not args.mp3.exists():
        sys.exit(f"Error: file not found: {args.mp3}")

    try:
        asyncio.run(main(single_mp3=args.mp3))
    except KeyboardInterrupt:
        print("\nInterrupt received — stopping after current episode.")
