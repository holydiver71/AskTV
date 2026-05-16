#!/usr/bin/env python3
"""Redact listener postal addresses from FRS transcript segments.

Redacts house number + street name (e.g. "224 Chester Road") replacing with
[redacted address].  Area / city / region info is preserved.

The BBC Radio 1 broadcaster address (BBC Radio 1, London, W1A4WW) is never
redacted.

Handles:
  - Single-segment addresses (number + street type)
  - "No. N" / "number N" prefix addresses (with or without standard street type)
  - Written house numbers ("Five Somerdale Gardens")
  - Flat/apartment prefixes ("Flat One, 7 Travis Place")
  - Multi-segment splits where the street name or type bleeds into the next tag

Run from workspace root:
    python scripts/redact_addresses.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

JSON_DIR = Path("data/episodes/1980/")
LOG_DIR = Path("logs/")
LOG_FILE = LOG_DIR / "redact_addresses.log"

REDACTION = "[redacted address]"

# Segments containing this string belong to the broadcaster — never redact
_BBC_SAFE = re.compile(r"BBC Radio 1")

# ---------------------------------------------------------------------------
# Regex building blocks
# ---------------------------------------------------------------------------

_STREET_TYPES = (
    r"Road|Street|Avenue|Lane|Gardens?|Garden|Park|Way|Close|Drive|"
    r"Terrace|Place|Court|Crescent|Grove|Hill|Rise|Walk|Row|Green|"
    r"Square|Mews|Gate|End|View|Heights?|Estate|House|Cottage|Farm|"
    r"Alley|Yard|Broadway|Queensway|Bypass|Boulevard|Kiln|Passage"
)

_WRITTEN_NUMS = (
    r"One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|"
    r"Eleven|Twelve|Thirteen|Fourteen|Fifteen|Sixteen|Seventeen|"
    r"Eighteen|Nineteen|Twenty"
)

# Optional "Flat N, " prefix (flat/apartment number)
_FLAT_PREFIX = (
    rf"(?:Flat\s+(?:\d+|{_WRITTEN_NUMS}|[A-Z])\s*,\s*)?"
)

# Street name body: 0-5 consecutive Title-Case words (stops at comma / lowercase)
_STREET_NAME_BODY = r"(?:[A-Z][\w']*(?:\s+[A-Z][\w']*){0,5})"

# ---------------------------------------------------------------------------
# Pattern A: digit house-number + optional words + street type
# e.g. "224 Chester Road", "19 The Old Garden", "202 East Lancashire Road"
# ---------------------------------------------------------------------------
_ADDR_DIGIT = re.compile(
    _FLAT_PREFIX +
    rf"(?<!\d)\b(\d{{1,4}})\s+"       # house number (1-4 digits)
    rf"(?:[A-Z][\w']*\s+){{0,5}}"     # 0-5 street-name words
    rf"(?:{_STREET_TYPES})\b"          # street type terminator
)

# ---------------------------------------------------------------------------
# Pattern B: written house-number + optional words + street type
# e.g. "Five Somerdale Gardens"
# ---------------------------------------------------------------------------
_ADDR_WRITTEN = re.compile(
    _FLAT_PREFIX +
    rf"\b({_WRITTEN_NUMS})\s+"
    rf"(?:[A-Z][\w']*\s+){{0,5}}"
    rf"(?:{_STREET_TYPES})\b"
)

# ---------------------------------------------------------------------------
# Pattern C: "No." / "number" prefix + digit + Title-Case words
# Catches non-standard street types too: "No. 40 Queensway", "No. 90 Lime Kiln"
# ---------------------------------------------------------------------------
_ADDR_PREFIX = re.compile(
    _FLAT_PREFIX +
    rf"\b(?:No\.?\s+|number\s+)(\d{{1,4}})\s+"
    rf"{_STREET_NAME_BODY}"
)

# ---------------------------------------------------------------------------
# Multi-segment helpers
# ---------------------------------------------------------------------------

# A segment whose text ends with what looks like an address fragment that hasn't
# finished yet (no street-type suffix, but the text ends with Title-Case words
# after a house number).  Used to detect the "No. 5 Green Lodge" case where
# "Terrace" is on the next segment.
_INCOMPLETE_ADDR_END = re.compile(
    rf"(?:(?:No\.?\s+|number\s+)?(?:\d{{1,4}}|{_WRITTEN_NUMS}))\s+"
    rf"[A-Z][\w']+(?:\s+[A-Z][\w']+){{0,4}}\s*,?\s*$"
)

# A segment whose text *starts* with a street-type word (dangling continuation)
# e.g. "Terrace in Glasgow, ..."
_STARTS_WITH_STREET_TYPE = re.compile(
    rf"^(?:{_STREET_TYPES})\b"
)

# ---------------------------------------------------------------------------
# Core redaction logic
# ---------------------------------------------------------------------------


def _redact_segment(text: str) -> tuple[str, bool]:
    """Apply address redaction patterns to a single text string.

    Returns (new_text, changed).  Segments containing the BBC address are
    left untouched.
    """
    if _BBC_SAFE.search(text):
        return text, False

    original = text
    # Apply C first (most specific — handles non-standard street types too)
    text = _ADDR_PREFIX.sub(REDACTION, text)
    # Then A and B
    text = _ADDR_DIGIT.sub(REDACTION, text)
    text = _ADDR_WRITTEN.sub(REDACTION, text)

    return text, text != original


def redact_transcript(segments: list[dict]) -> tuple[list[dict], int]:
    """Redact addresses in a list of transcript segment dicts.

    Mutates a copy; returns (new_segments, redaction_count).
    """
    segments = [dict(s) for s in segments]  # shallow copy each segment
    redacted_count = 0

    # --- Pass 1: single-segment inline redaction ---
    for i, seg in enumerate(segments):
        if seg.get("type") == "music":
            continue
        new_text, changed = _redact_segment(seg["text"])
        if changed:
            seg["text"] = new_text
            segments[i] = seg
            redacted_count += 1

    # --- Pass 2: multi-segment — strip dangling street-type from next segment ---
    # Handles: "No. 5 Green Lodge" → [redacted address] / "Terrace in Glasgow"
    for i in range(len(segments) - 1):
        seg = segments[i]
        next_seg = segments[i + 1]
        if seg.get("type") == "music" or next_seg.get("type") == "music":
            continue

        # Only act when the current segment was *already* redacted and the
        # original text ended with an incomplete-looking address
        if REDACTION not in seg.get("text", ""):
            continue

        next_text = next_seg.get("text", "").strip()
        m = _STARTS_WITH_STREET_TYPE.match(next_text)
        if not m:
            continue

        # Strip the leading street-type word and any following punctuation/space
        stripped = next_text[m.end():].lstrip(" ,")
        if stripped:
            next_seg["text"] = stripped
            segments[i + 1] = next_seg
            redacted_count += 1

    return segments, redacted_count


# ---------------------------------------------------------------------------
# File I/O
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


def process_file(path: Path, dry_run: bool = False) -> int:
    """Process a single episode JSON file.  Returns number of redactions made."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    transcript = data.get("transcript")
    if not transcript:
        return 0

    new_segments, count = redact_transcript(transcript)
    if count == 0:
        return 0

    data["transcript"] = new_segments

    if not dry_run:
        _atomic_write(path, data)

    label = "[DRY RUN] " if dry_run else ""
    _log(f"{label}{path.name}: {count} redaction(s)")
    return count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    episode_files = sorted(JSON_DIR.glob("*.json"))

    if not episode_files:
        _log(f"No JSON files found in {JSON_DIR}")
        sys.exit(1)

    total = 0
    for fp in episode_files:
        count = process_file(fp, dry_run=dry_run)
        total += count

    mode = "DRY RUN — " if dry_run else ""
    _log(f"\n{mode}Total redactions across {len(episode_files)} episodes: {total}")


if __name__ == "__main__":
    main()
