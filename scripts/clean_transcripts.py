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
# Additionally, any single segment whose duration exceeds 120 s is always a
# hallucination regardless of word count — no real speech segment lasts that
# long; Whisper is hallucinating over a music bed.
_HALLUCINATION_MIN_RUN = 3
_HALLUCINATION_LONG_SEG_SECS = 25.0
_HALLUCINATION_LONG_SEG_MAX_WORDS = 6
_HALLUCINATION_EXTREME_SEG_SECS = 120.0


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
    3. **Extreme-duration segment**: a single segment whose duration exceeds
       _HALLUCINATION_EXTREME_SEG_SECS regardless of word count — Whisper is
       stretching real speech over a music bed.  The text is genuine so the
       segment is *trimmed* to a realistic duration (0.6 s/word, min 3 s) rather
       than dropped, preserving the commentary while leaving a gap for Phase 2
       to fill with a [Music] placeholder.

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

    # Step 2: handle long-segment and extreme-duration hallucinations
    trimmed = 0
    new_transcript = []
    for idx, seg in enumerate(transcript):
        if idx in hallucination_indices:
            # Already marked as run-repetition — drop it
            new_transcript.append(None)
            continue
        if seg.get("type") == "music":
            new_transcript.append(seg)
            continue
        duration = float(seg.get("end", 0)) - float(seg.get("start", 0))
        word_count = len(seg.get("text", "").split())
        if duration >= _HALLUCINATION_EXTREME_SEG_SECS:
            # Text is real speech; Whisper stretched the end across the music.
            # Trim to a realistic duration so Phase 2 can fill the gap.
            realistic_end = float(seg["start"]) + max(word_count * 0.6, 3.0)
            seg = dict(seg)
            seg["end"] = round(realistic_end, 2)
            trimmed += 1
            new_transcript.append(seg)
        elif duration >= _HALLUCINATION_LONG_SEG_SECS and word_count <= _HALLUCINATION_LONG_SEG_MAX_WORDS:
            hallucination_indices.add(idx)
            new_transcript.append(None)
        else:
            new_transcript.append(seg)

    cleaned = [s for s in new_transcript if s is not None]
    removed = len(transcript) - len(cleaned)

    if not removed and not trimmed:
        return data, 0

    data["transcript"] = cleaned
    return data, removed + trimmed


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Phase 2 — Window calculation (step 6)
# ---------------------------------------------------------------------------

# Minimum plausible song duration — we won't look for speech before this
# many seconds have elapsed from song_start.
_MIN_SONG_SECS = 90.0

# A segment is considered "speech-like" if its duration is at most this many
# seconds.  With VAD filter enabled, Whisper only produces speech segments, so
# they're always short; music doesn't appear in the transcript at all.
_SPEECH_SEG_MAX_SECS = 8.0

# We need at least this many consecutive speech-like segments to declare that
# Tommy has returned (guards against a single short lyric slip-through).
_SPEECH_RESUME_MIN_CONSECUTIVE = 2

# A silence/gap between consecutive transcript segments larger than this (in
# seconds) is treated as music playing.  Covers the case where Phase-1b already
# stripped the Whisper hallucination segment, leaving only an empty gap.
_MUSIC_GAP_MIN_SECS = 30.0

# In _find_music_start, a segment must be at least this long to be considered a
# Whisper music-bed hallucination blob (vs. legitimate speech).  Tommy regularly
# speaks in 8-15 s segments; actual music blobs span hundreds of seconds.
_MUSIC_BLOB_MIN_SECS = 60.0


def _find_speech_resume(
    transcript: list[dict],
    song_start: float,
    hard_cap: float,
) -> float:
    """Return the timestamp where speech resumes after a song starts.

    Scans transcript segments that begin after ``song_start + _MIN_SONG_SECS``
    looking for ``_SPEECH_RESUME_MIN_CONSECUTIVE`` consecutive speech-like
    segments (duration ≤ _SPEECH_SEG_MAX_SECS) that also lie before
    ``hard_cap``.  Returns the start time of the first such cluster, or
    ``hard_cap`` if none is found.

    This prevents the muzzle window from extending over Tommy's inter-track
    commentary when the gap between two verified_timestamps is large.
    """
    earliest = song_start + _MIN_SONG_SECS
    candidates = [
        s for s in transcript
        if s.get("type") != "music"
        and float(s["start"]) >= earliest
        and float(s["start"]) < hard_cap
    ]

    for i, seg in enumerate(candidates):
        dur = float(seg["end"]) - float(seg["start"])
        if dur > _SPEECH_SEG_MAX_SECS:
            continue
        # Check the required number of consecutive short segments.
        # "Consecutive" means both short-duration AND close in time — a gap
        # larger than _MUSIC_GAP_MIN_SECS between adjacent candidates means
        # there is music between them; they should NOT count as a run.
        run_ok = True
        prev_end = float(seg["end"])
        for j in range(1, _SPEECH_RESUME_MIN_CONSECUTIVE):
            if i + j >= len(candidates):
                run_ok = False
                break
            nxt = candidates[i + j]
            nxt_dur = float(nxt["end"]) - float(nxt["start"])
            gap = float(nxt["start"]) - prev_end
            if nxt_dur > _SPEECH_SEG_MAX_SECS or gap >= _MUSIC_GAP_MIN_SECS:
                run_ok = False
                break
            prev_end = float(nxt["end"])
        if run_ok:
            return float(seg["start"])

    return hard_cap


def _find_music_start(
    transcript: list[dict],
    nominal_start: float,
    hard_cap: float,
) -> float:
    """Return the timestamp where music actually begins at or after nominal_start.

    verified_timestamp is sometimes set via transcript back-announcement search,
    meaning it points to when Tommy *mentions* an artist rather than when the
    music starts.  This function pushes past any speech cluster at nominal_start
    to the actual music boundary by detecting:

    * A segment whose duration exceeds _SPEECH_SEG_MAX_SECS — a Whisper
      hallucination on a music bed that Phase-1b did not strip (e.g. a sentence
      with more than _HALLUCINATION_LONG_SEG_MAX_WORDS words).
    * A gap between consecutive segments larger than _MUSIC_GAP_MIN_SECS — the
      gap left after Phase-1b removed the hallucination segment.

    Returns nominal_start if the transcript immediately gaps/hallucinates there
    (i.e. music started before Tommy spoke), or the end of the last speech
    segment before the music boundary.
    """
    segs = sorted(
        [
            s for s in transcript
            if s.get("type") != "music"
            and float(s["start"]) >= nominal_start
            and float(s["start"]) < hard_cap
        ],
        key=lambda s: float(s["start"]),
    )

    if not segs:
        return nominal_start

    # If the transcript jumps straight into a gap at nominal_start, music is there
    if float(segs[0]["start"]) - nominal_start >= _MUSIC_GAP_MIN_SECS:
        return nominal_start

    prev_end = nominal_start
    for seg in segs:
        gap = float(seg["start"]) - prev_end
        if gap >= _MUSIC_GAP_MIN_SECS:
            # Gap between last speech and this segment — music is in the gap
            return prev_end
        duration = float(seg["end"]) - float(seg["start"])
        if duration > _MUSIC_BLOB_MIN_SECS:
            # Long hallucination segment — music starts here
            return float(seg["start"])
        prev_end = float(seg["end"])

    # All scanned segments were speech — music begins after the last one
    return prev_end


def build_music_windows(
    track_listing: list[dict],
    transcript: list[dict],
    audio_end: float,
) -> list[dict]:
    """Compute [song_start, song_end] windows for tracks with verified_timestamp.

    The window end is determined by where speech *actually resumes* in the
    transcript after the song starts, rather than blindly extending to the
    next track's verified_timestamp.  This prevents Tommy's inter-track
    commentary from being swallowed when there is a large gap between two
    verified timestamps (e.g. because Shazam missed a session track).

    Args:
        track_listing: The episode's track_listing array.
        transcript:    The current transcript array (used to locate speech).
        audio_end:     Duration of the audio in seconds.

    Returns:
        A list of window dicts (empty when no verified timestamps present):
            {
                "start":  float,
                "end":    float,
                "artist": str,
                "track":  str,
            }
    """
    verified = [t for t in track_listing if "verified_timestamp" in t]
    if not verified:
        return []  # Phase-2 gate

    # Sort by timestamp so the hard-cap calculation is always forward-looking.
    verified = sorted(verified, key=lambda t: float(t["verified_timestamp"]))

    windows: list[dict] = []
    for i, track in enumerate(verified):
        nominal_start = float(track["verified_timestamp"])

        # Hard cap: never extend past 5 s before the next verified track.
        if i + 1 < len(verified):
            hard_cap = float(verified[i + 1]["verified_timestamp"]) - 5.0
        else:
            hard_cap = audio_end

        # Push past any back-announcement speech at nominal_start to find
        # where the music actually is (gap or long hallucination segment).
        song_start = _find_music_start(transcript, nominal_start, hard_cap)

        # Find where speech actually resumes after the music, within that cap.
        song_end = _find_speech_resume(transcript, song_start, hard_cap)

        # Clamp: song_end must be strictly greater than song_start.
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

    windows = build_music_windows(track_listing, transcript, audio_end)
    if windows:
        _log(
            f"[{date}] Phase 2 active — {len(windows)} verified track window(s) computed"
        )

        # Steps 7-10: replace lyric segments with a single music placeholder
        # Rebuild transcript: keep segments outside all windows, then insert
        # a placeholder for EVERY non-degenerate window (even those whose
        # enclosed segments were already stripped by Phase-1b hallucination
        # removal — the gap must still be marked with a music placeholder).
        new_transcript = []
        total_muzzled = 0
        for seg in transcript:
            enclosed = any(
                seg["start"] >= w["start"] and seg["end"] <= w["end"]
                for w in windows
                if w["end"] > w["start"]
            )
            if enclosed:
                total_muzzled += 1
            else:
                new_transcript.append(seg)

        # Always add a placeholder for every non-degenerate window
        for w in windows:
            if w["end"] <= w["start"]:
                continue
            new_transcript.append({
                "start": w["start"],
                "end": w["end"],
                "text": "[Music]",
                "type": "music",
            })
            track_label = f"'{w['artist']} – {w['track']}'" if w["artist"] else f"'{w['track']}'"
            muzzled_in_window = sum(
                1 for s in transcript
                if s["start"] >= w["start"] and s["end"] <= w["end"]
            )
            if muzzled_in_window:
                _log(f"[{date}] Muzzled {muzzled_in_window} segment(s) in window anchored by {track_label} [{w['start']:.1f}–{w['end']:.1f}s]")

        # Sort by start time so placeholders land in the right position
        new_transcript.sort(key=lambda s: float(s["start"]))

        active_windows = sum(1 for w in windows if w["end"] > w["start"])
        _log(
            f"[{date}] Total muzzled: {total_muzzled} segment(s) → "
            f"{active_windows} placeholder(s) inserted"
        )
        data["transcript"] = new_transcript
        modified = True

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
