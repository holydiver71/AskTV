#!/usr/bin/env python3
"""Clean raw Whisper transcripts in two phases.

Phase 1 (immediate)  — strip ellipsis-only silence placeholders.
Phase 2 (post-Shazam) — muzzle song-lyric segments using verified_timestamp
                         windows; self-gates on presence of verified_timestamp
                         fields in track_listing.

Run from the workspace root:
    python scripts/clean_transcripts.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JSON_DIR = Path("data/episodes/1980/")
LOG_DIR = Path("logs/")
LOG_FILE = LOG_DIR / "clean_transcripts.log"

_ELLIPSIS_RE = re.compile(r"^[.\s]*$")  # empty, whitespace-only, or pure dots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log(message: str) -> None:
    print(message)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _is_ellipsis(text: str) -> bool:
    return bool(_ELLIPSIS_RE.match(text))


# ---------------------------------------------------------------------------
# Phase 1 — Ellipsis stripper (steps 1-5)
# ---------------------------------------------------------------------------


def strip_ellipsis(data: dict) -> tuple[dict, int]:
    """Return (updated_data, count_removed).  Safe to call on data without a
    transcript key — returns unchanged data with count 0."""
    transcript = data.get("transcript")
    if not transcript:
        return data, 0

    cleaned = [s for s in transcript if not _is_ellipsis(s.get("text", ""))]
    removed = len(transcript) - len(cleaned)
    data["transcript"] = cleaned
    return data, removed


# ---------------------------------------------------------------------------
# Phase 2 — Window calculation (step 6)
# ---------------------------------------------------------------------------


def build_music_windows(track_listing: list[dict], audio_end: float) -> list[dict]:
    """Compute [song_start, song_end] windows for tracks with verified_timestamp.

    Args:
        track_listing: The episode's track_listing array.
        audio_end: Duration of the audio in seconds, used as the upper bound
                   for the last verified track.  Derive from the last
                   transcript segment's `end` value when actual MP3 duration
                   is not available.

    Returns:
        A list of window dicts (may be empty when no verified timestamps
        are present — this is the Phase-2 self-gate):
            {
                "start":  float,   # verified_timestamp of this track
                "end":    float,   # next track's verified_timestamp - 5 s,
                                   #  or audio_end for the last track
                "artist": str,
                "track":  str,
            }
    """
    verified = [t for t in track_listing if "verified_timestamp" in t]
    if not verified:
        return []  # Phase-2 gate: nothing to do until Shazam has run

    windows: list[dict] = []
    for i, track in enumerate(verified):
        song_start = float(track["verified_timestamp"])

        if i + 1 < len(verified):
            # Leave a 5-second buffer before the next track starts so any
            # Tommy intro speech immediately preceding the track isn't lost.
            song_end = float(verified[i + 1]["verified_timestamp"]) - 5.0
        else:
            song_end = audio_end

        # Clamp: song_end must be strictly greater than song_start
        if song_end <= song_start:
            song_end = song_start  # degenerate window — muzzler will skip

        windows.append(
            {
                "start": song_start,
                "end": song_end,
                "artist": track.get("artist") or "",
                "track": track.get("track") or "",
            }
        )

    return windows


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------


def process_file(json_path: Path) -> bool:
    """Process one JSON file.  Returns True on success."""
    try:
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        _log(f"[ERROR] Could not read {json_path.name}: {exc}")
        return False

    date = data.get("show", {}).get("date") or json_path.stem.replace("FRS ", "")
    modified = False

    # ── Phase 1: strip ellipsis segments ────────────────────────────────────
    data, ellipsis_count = strip_ellipsis(data)
    if ellipsis_count:
        _log(f"[{date}] Removed {ellipsis_count} ellipsis segment(s)")
        modified = True

    # ── Phase 2: compute music windows (step 6) ─────────────────────────────
    track_listing = data.get("track_listing") or []
    transcript = data.get("transcript") or []

    audio_end = float(transcript[-1]["end"]) if transcript else 0.0

    windows = build_music_windows(track_listing, audio_end)
    if windows:
        _log(
            f"[{date}] Phase 2 active — {len(windows)} verified track window(s) computed"
        )
        for w in windows:
            _log(
                f"         {w['artist']} – {w['track']}: "
                f"{w['start']:.1f}s → {w['end']:.1f}s"
            )
        # Steps 7-10 (segment removal and placeholder insertion) go here.

    if modified:
        _atomic_write(json_path, data)

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    json_files = sorted(JSON_DIR.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {JSON_DIR}")
        return 1

    print(f"Processing {len(json_files)} episode(s) in {JSON_DIR}…")
    success = errors = 0

    for json_path in json_files:
        ok = process_file(json_path)
        if ok:
            success += 1
        else:
            errors += 1

    print(f"\nDone — {success} OK, {errors} error(s).  Log: {LOG_FILE}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
