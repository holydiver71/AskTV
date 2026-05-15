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

# Whisper hallucination detection
# A run of 3+ consecutive segments with identical (normalised) text, OR a
# segment whose duration is ≥ 25 s and whose text is ≤ 6 words, is treated
# as a hallucination (the classic 30-second music-bed repetition pattern).
_HALLUCINATION_MIN_RUN = 3
_HALLUCINATION_LONG_SEG_SECS = 25.0
_HALLUCINATION_LONG_SEG_MAX_WORDS = 6


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
# Phase 1b — Hallucination stripper
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


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace — used for hallucination comparison."""
    return " ".join(text.lower().split())


def strip_hallucinations(data: dict) -> tuple[dict, int]:
    """Detect and remove Whisper hallucination runs.

    Two patterns are caught:
    1. **Run repetition**: a consecutive run of ≥ _HALLUCINATION_MIN_RUN
       segments whose normalised text is identical.  The entire run is dropped.
    2. **Long-segment placeholder**: a single segment whose duration is
       ≥ _HALLUCINATION_LONG_SEG_SECS and whose text contains at most
       _HALLUCINATION_LONG_SEG_MAX_WORDS words (e.g. "thomas vance" for 30 s).
       These are dropped individually.

    Music placeholder segments (``"type": "music"``) are always preserved.
    """
    transcript = data.get("transcript")
    if not transcript:
        return data, 0

    # Step 1: mark run-repetition candidates
    hallucination_indices: set[int] = set()

    i = 0
    while i < len(transcript):
        seg = transcript[i]
        if seg.get("type") == "music":
            i += 1
            continue
        norm = _normalise(seg.get("text", ""))
        # find run
        j = i + 1
        while j < len(transcript) and transcript[j].get("type") != "music" and _normalise(transcript[j].get("text", "")) == norm:
            j += 1
        run_len = j - i
        if run_len >= _HALLUCINATION_MIN_RUN:
            for k in range(i, j):
                hallucination_indices.add(k)
        i = j if run_len > 1 else i + 1

    # Step 2: mark long-segment hallucinations
    for idx, seg in enumerate(transcript):
        if seg.get("type") == "music":
            continue
        duration = float(seg.get("end", 0)) - float(seg.get("start", 0))
        word_count = len(seg.get("text", "").split())
        if duration >= _HALLUCINATION_LONG_SEG_SECS and word_count <= _HALLUCINATION_LONG_SEG_MAX_WORDS:
            hallucination_indices.add(idx)

    if not hallucination_indices:
        return data, 0

    cleaned = [s for i, s in enumerate(transcript) if i not in hallucination_indices]
    data["transcript"] = cleaned
    return data, len(hallucination_indices)


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

    # ── Phase 1b: strip hallucination runs ──────────────────────────────────
    data, hallucination_count = strip_hallucinations(data)
    if hallucination_count:
        _log(f"[{date}] Removed {hallucination_count} hallucination segment(s)")
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

        # Steps 7-10: replace lyric segments with a single music placeholder
        new_transcript: list[dict] = []
        total_muzzled = 0

        for w in windows:
            w_start = w["start"]
            w_end = w["end"]
            label = f"[Music: {w['artist']} – {w['track']}]" if w["artist"] else f"[Music: {w['track']}]"

            # Count segments fully enclosed in this window
            muzzled = sum(
                1 for s in transcript
                if s["start"] >= w_start and s["end"] <= w_end
            )
            total_muzzled += muzzled
            if muzzled:
                _log(f"[{date}] Muzzled {muzzled} segment(s) for '{w['artist']} – {w['track']}'")

        # Rebuild transcript: keep segments outside all windows, insert placeholders
        used_windows: set[int] = set()
        for seg in transcript:
            enclosed_in = None
            for i, w in enumerate(windows):
                if seg["start"] >= w["start"] and seg["end"] <= w["end"]:
                    enclosed_in = i
                    break
            if enclosed_in is None:
                new_transcript.append(seg)
            else:
                if enclosed_in not in used_windows:
                    used_windows.add(enclosed_in)
                    w = windows[enclosed_in]
                    label = (
                        f"[Music: {w['artist']} – {w['track']}]"
                        if w["artist"]
                        else f"[Music: {w['track']}]"
                    )
                    new_transcript.append({
                        "start": w["start"],
                        "end": w["end"],
                        "text": label,
                        "type": "music",
                    })

        if total_muzzled:
            data["transcript"] = new_transcript
            modified = True
            _log(f"[{date}] Total muzzled: {total_muzzled} segment(s) → {len(used_windows)} placeholder(s) inserted")

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
