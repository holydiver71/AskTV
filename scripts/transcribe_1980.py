#!/usr/bin/env python3
"""Transcribe 1980 MP3s and append `transcript` to matching JSON files.

Follows the Phase1a plan: idempotent, atomic write-back, graceful SIGINT.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover - runtime environment dependent
    print("faster-whisper is required. Install it in your .venv: pip install faster-whisper")
    raise


STOP_REQUESTED = False


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\nInterrupt received — will stop after current file finishes.")


def fmt_duration(seconds: float) -> str:
    """Return a human-readable duration string."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{seconds:.1f}s"


def log_error(log_file: Path, message: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with open(log_file, "a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {message}\n")


def find_date_in_name(name: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


# Initial prompt primes Whisper with show-specific proper nouns so it
# transcribes band names, Tommy's sign-off phrases, and BBC terminology
# correctly instead of guessing phonetic equivalents.
_INITIAL_PROMPT = (
    "BBC Radio 1. The Friday Rock Show with Tommy Vance. "
    "Featuring sessions and tracks from artists including "
    "AC/DC, Motörhead, Syd Barrett, Wishbone Ash, Praying Mantis, "
    "Ted Nugent, Frank Zappa, Bad Company, Pretenders, Todd Rundgren. "
    "This is Tommy Vance on Radio 1."
)

# VAD parameters tuned for radio: music beds mean we need a slightly longer
# minimum silence window before declaring a speech boundary.
_VAD_PARAMETERS = {
    "threshold": 0.35,           # lower = catch quieter speech over music
    "min_speech_duration_ms": 250,
    "min_silence_duration_ms": 600,
    "speech_pad_ms": 400,        # extra padding around speech windows
}


def transcribe_file(model: WhisperModel, mp3_path: Path) -> list[dict]:
    segments_gen, info = model.transcribe(
        str(mp3_path),
        language="en",
        beam_size=5,
        initial_prompt=_INITIAL_PROMPT,
        # Prevent the previous segment's text being fed back as a prompt —
        # this is the root cause of the "thomas vance" 30-second loop.
        condition_on_previous_text=False,
        # Silero VAD: skip pure-music windows, focus computation on speech.
        vad_filter=True,
        vad_parameters=_VAD_PARAMETERS,
        # More permissive silence threshold so short interjections over
        # music aren't silently discarded (default is 0.6).
        no_speech_threshold=0.4,
        # Temperature fallback: if greedy (0) produces low-confidence output
        # Whisper retries at 0.2 then 0.4 before giving up.
        temperature=[0, 0.2, 0.4],
    )
    duration = info.duration
    out: list[dict] = []
    last_pct = -1
    for seg in segments_gen:
        out.append({"start": float(seg.start), "end": float(seg.end), "text": seg.text.strip()})
        if duration > 0:
            pct = min(int((seg.end / duration) * 100), 100)
            if pct >= last_pct + 10:
                last_pct = pct
                print(f"  Transcribing... {pct:3d}%  ({len(out)} segments)", end="\r", flush=True)
    print(f"  Transcribing... 100%  ({len(out)} segments) ✓          ")
    return out


def atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def main() -> int:
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(description="Transcribe 1980 MP3s and append transcript to JSON files.")
    parser.add_argument("mp3", nargs="?", help="Optional path or filename of a single MP3 to process")
    parser.add_argument(
        "--retranscribe",
        action="store_true",
        help="Re-transcribe files that already have a transcript (overwrites existing transcript)",
    )
    args = parser.parse_args()

    AUDIO_DIR = Path("FRSAudio/128kbps/1980/")
    JSON_DIR = Path("data/episodes/1980/")
    LOG_FILE = Path("logs/transcription_errors.log")

    # Ensure logs directory exists before anything can fail
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── Model load ──────────────────────────────────────────────────────────
    print("Loading Whisper model (large-v3 · CPU · int8)...")
    t_model = time.perf_counter()
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")
    print(f"Model ready  [{fmt_duration(time.perf_counter() - t_model)}]\n")

    # ── File discovery ──────────────────────────────────────────────────────
    if args.mp3:
        candidate = Path(args.mp3)
        if not candidate.exists():
            candidate_in_dir = AUDIO_DIR / args.mp3
            if candidate_in_dir.exists():
                candidate = candidate_in_dir
            else:
                print(f"ERROR: Specified MP3 not found: {args.mp3}")
                return 2
        mp3s = [candidate]
    else:
        mp3s = sorted(AUDIO_DIR.glob("*.mp3"))

    total = len(mp3s)
    if total == 0:
        print("No MP3s found to process.")
        return 1

    print(f"Found {total} MP3(s) to process.")
    print("─" * 52)

    # ── Main loop ───────────────────────────────────────────────────────────
    processed = skipped = errors = 0
    t_run = time.perf_counter()

    for idx, mp3 in enumerate(mp3s, start=1):
        if STOP_REQUESTED:
            print("\nStopping before next file.")
            break

        date = find_date_in_name(mp3.name)
        display = date or mp3.name
        print(f"\n[{idx}/{total}] {display}")

        if not date:
            msg = f"Skipping {mp3} — couldn't extract date from filename"
            print(f"  WARNING: {msg}")
            log_error(LOG_FILE, msg)
            errors += 1
            continue

        json_path = JSON_DIR / f"FRS {date}.json"
        if not json_path.exists():
            msg = f"No JSON found for {date} (expected {json_path})"
            print(f"  WARNING: {msg}")
            log_error(LOG_FILE, msg)
            errors += 1
            continue

        print(f"  JSON     : {json_path.name}")

        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            msg = f"Failed to read {json_path}: {exc}"
            print(f"  ERROR: {msg}")
            log_error(LOG_FILE, msg)
            errors += 1
            continue

        if "transcript" in data and not args.retranscribe:
            print(f"  Skipped  — already transcribed ({len(data['transcript'])} segments)")
            skipped += 1
            continue
        elif "transcript" in data and args.retranscribe:
            print(f"  Re-transcribing (had {len(data['transcript'])} segments)...")

        try:
            t_file = time.perf_counter()
            segments = transcribe_file(model, mp3)
            data["transcript"] = segments
            print(f"  Writing JSON ({len(segments)} segments)...", end=" ", flush=True)
            atomic_write(json_path, data)
            elapsed = fmt_duration(time.perf_counter() - t_file)
            print(f"done  [{elapsed}]")
            processed += 1
        except Exception as exc:
            msg = f"Error transcribing {mp3}: {exc}"
            print(f"  ERROR: {msg}")
            log_error(LOG_FILE, msg)
            errors += 1
            continue

        if STOP_REQUESTED:
            print("Stop requested — exiting cleanly.")
            break

    # ── Summary ─────────────────────────────────────────────────────────────
    total_time = fmt_duration(time.perf_counter() - t_run)
    print(f"\n{'─' * 52}")
    print(f"Run complete  [{total_time}]")
    print(f"  Processed : {processed}")
    print(f"  Skipped   : {skipped}  (already had transcript — use --retranscribe to overwrite)")
    print(f"  Errors    : {errors}")
    if errors:
        print(f"  Log       : {LOG_FILE}")
    print("─" * 52)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
