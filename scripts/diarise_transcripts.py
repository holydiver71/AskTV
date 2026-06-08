#!/usr/bin/env python3
"""Tag transcript segments with "source": "TV" or "source": "uncertain".

Scores each speech segment's audio directly against Tommy Vance's saved voice
embedding using resemblyzer cosine similarity. Per-segment scoring means a
single non-TV voice cannot inflate its label by sharing a pyannote cluster with
Tommy Vance.

Run from the workspace root:
    python scripts/diarise_transcripts.py --year 1981
    python scripts/diarise_transcripts.py --mp3 "FRSAudio/128kbps/1981/FRS 1981-04-10_128kps.mp3"

Idempotent: skip already-tagged episodes by default; use --retag to overwrite.
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

import numpy as np
import torch
from dotenv import load_dotenv
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav

load_dotenv()

TV_EMBEDDING_PATH = Path("data/tommy_vance_embedding.npy")
LOG_FILE = Path("logs/diarisation_errors.log")
TV_SIMILARITY_THRESHOLD = 0.65
MIN_SEGMENT_SECS = 1.0  # minimum segment duration for a reliable voice embedding

STOP_REQUESTED = False


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\nInterrupt received — finishing current episode then stopping.")


def log_error(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {message}\n")
    print(f"  ERROR: {message}")


def atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def find_date_in_name(name: str) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def cosine_similarity(a: np.ndarray | tuple | list, b: np.ndarray | tuple | list) -> float:
    a = np.asarray(a)
    b = np.asarray(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def resolve_device(requested: str) -> torch.device:
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(requested)


def load_tv_embedding(path: Path = TV_EMBEDDING_PATH) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(
            f"Tommy Vance embedding not found at {path}.\n"
            "Run 'python scripts/build_tv_embedding.py' first."
        )
    embedding = np.load(path)
    print(f"Loaded TV embedding from {path}  shape={embedding.shape}")
    return embedding


def tag_segments(
    mp3_path: Path,
    transcript: list[dict],
    encoder: VoiceEncoder,
    tv_embedding: np.ndarray,
    similarity_threshold: float = TV_SIMILARITY_THRESHOLD,
) -> int:
    """Score each non-music segment directly against the TV voice embedding.

    Audio is converted to float32 numpy in-memory (no temp files).
    Segments shorter than MIN_SEGMENT_SECS are tagged 'uncertain' without
    scoring — resemblyzer is unreliable on very short clips.
    """
    audio = AudioSegment.from_mp3(str(mp3_path))
    tv_count = 0
    speech_segs = [s for s in transcript if s.get("type") != "music"]
    total = len(speech_segs)
    tagged = 0

    for seg in transcript:
        if seg.get("type") == "music":
            continue

        tagged += 1
        if tagged == 1 or tagged == total or tagged % 25 == 0:
            print(f"  Scoring segment {tagged}/{total}...")

        start_s = float(seg["start"])
        end_s = float(seg["end"])
        duration = end_s - start_s

        if duration < MIN_SEGMENT_SECS:
            seg["source"] = "uncertain"
            continue

        clip = audio[int(start_s * 1000): int(end_s * 1000)]
        clip = clip.set_frame_rate(16000).set_channels(1)

        try:
            samples = np.array(clip.get_array_of_samples(), dtype=np.float32)
            samples /= float(2 ** (clip.sample_width * 8 - 1))
            wav = preprocess_wav(samples, source_sr=16000)
            embedding = encoder.embed_utterance(wav)
        except Exception as exc:
            log_error(
                f"Segment {start_s:.2f}-{end_s:.2f} in {mp3_path.name}: embedding failed: {exc}"
            )
            seg["source"] = "uncertain"
            continue

        similarity = cosine_similarity(embedding, tv_embedding)
        seg["source"] = "TV" if similarity >= similarity_threshold else "uncertain"
        if seg["source"] == "TV":
            tv_count += 1

    return tv_count


def process_episode(
    encoder: VoiceEncoder,
    tv_embedding: np.ndarray,
    mp3_path: Path,
    json_path: Path,
    retag: bool = False,
    similarity_threshold: float = TV_SIMILARITY_THRESHOLD,
) -> str:
    """Process one episode: score each segment against TV embedding, write back."""
    print(f"Processing {mp3_path.name}")
    print(f"  JSON → {json_path.name}")

    try:
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        log_error(f"{json_path.name}: Failed to load JSON: {exc}")
        return "error"

    transcript = data.get("transcript", [])
    if not transcript:
        print("  No transcript — skipping.")
        return "skipped"

    speech_segments = [s for s in transcript if s.get("type") != "music"]
    print(
        f"  Transcript loaded: {len(transcript)} total segments, "
        f"{len(speech_segments)} speech segments"
    )

    already_tagged = any("source" in s for s in speech_segments)
    if already_tagged and not retag:
        print("  Already tagged — skipping. Use --retag to overwrite.")
        return "skipped"

    try:
        print("  Step 1/2: scoring segments against TV embedding...")
        tv_count = tag_segments(
            mp3_path, transcript, encoder, tv_embedding, similarity_threshold
        )
    except Exception as exc:
        log_error(f"{mp3_path.name}: Scoring failed: {exc}")
        return "error"

    total_speech = len(speech_segments)
    uncertain_count = total_speech - tv_count
    print(
        f"  Tagged {tv_count}/{total_speech} speech segments as 'TV' "
        f"({uncertain_count} as 'uncertain')"
    )

    print("  Step 2/2: writing JSON")
    data["transcript"] = transcript
    atomic_write(json_path, data)
    print(f"  Saved → {json_path.name}")
    return "tagged"


def main() -> int:
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(
        description="Tag transcript segments with source: TV or uncertain."
    )
    parser.add_argument(
        "--year",
        "-y",
        nargs="+",
        default=["1981"],
        metavar="YYYY",
        help="One or more years to process (e.g. --year 1980 1981)",
    )
    parser.add_argument(
        "mp3",
        nargs="?",
        help="Optional: path to a single MP3 to process instead of a whole year",
    )
    parser.add_argument(
        "--retag",
        action="store_true",
        help="Overwrite existing 'source' fields (default: skip already-tagged episodes)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=TV_SIMILARITY_THRESHOLD,
        help=(
            f"Per-segment cosine similarity threshold for TV identification "
            f"(default: {TV_SIMILARITY_THRESHOLD}). Segments scoring below this "
            f"are tagged 'uncertain'."
        ),
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=5.0,
        metavar="SECONDS",
        help="Seconds to pause between MP3s in batch mode (default: 5)",
    )
    parser.add_argument(
        "--ref-embedding",
        type=Path,
        default=TV_EMBEDDING_PATH,
        help=f"Path to Tommy Vance embedding file (default: {TV_EMBEDDING_PATH})",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="Runtime device for resemblyzer embeddings (default: auto)",
    )
    args = parser.parse_args()

    try:
        tv_embedding = load_tv_embedding(args.ref_embedding)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    device = resolve_device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        print("ERROR: --device cuda requested, but CUDA is not available on this machine.")
        return 1

    print("Loading resemblyzer voice encoder...")
    encoder = VoiceEncoder(device=device)
    print("Encoder ready.\n")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    grand_tagged = grand_skipped = grand_errors = 0

    if args.mp3:
        mp3_path = Path(args.mp3)
        if not mp3_path.exists():
            print(f"ERROR: MP3 not found: {mp3_path}")
            return 1

        date = find_date_in_name(mp3_path.name)
        if not date:
            print(f"ERROR: Could not extract date from filename: {mp3_path.name}")
            return 1

        year = date[:4]
        json_path = Path(f"data/episodes/{year}/FRS {date}.json")
        if not json_path.exists():
            print(f"ERROR: JSON not found: {json_path}")
            return 1

        status = process_episode(
            encoder,
            tv_embedding,
            mp3_path,
            json_path,
            args.retag,
            similarity_threshold=args.threshold,
        )
        print(f"\nResult: {status}")
        return 0

    for year in sorted(set(args.year)):
        audio_dir = Path(f"FRSAudio/128kbps/{year}/")
        json_dir = Path(f"data/episodes/{year}/")
        mp3s = sorted(audio_dir.glob("*.mp3"))

        if not mp3s:
            print(f"No MP3s found in {audio_dir}")
            continue

        print(f"\n{'═' * 52}")
        print(f"Year: {year}  ({len(mp3s)} episodes)")
        print("═" * 52)

        for idx, mp3_path in enumerate(mp3s, start=1):
            if STOP_REQUESTED:
                print("\nStopping.")
                break

            date = find_date_in_name(mp3_path.name)
            if not date:
                log_error(f"Could not extract date from {mp3_path.name}")
                grand_errors += 1
                continue

            json_path = json_dir / f"FRS {date}.json"
            if not json_path.exists():
                log_error(f"JSON not found for {date}: {json_path}")
                grand_errors += 1
                continue

            print(f"\n[{idx}/{len(mp3s)}] {date}")
            status = process_episode(
                encoder,
                tv_embedding,
                mp3_path,
                json_path,
                args.retag,
                similarity_threshold=args.threshold,
            )
            if status == "tagged":
                grand_tagged += 1
            elif status == "skipped":
                grand_skipped += 1
            else:
                grand_errors += 1

            if idx < len(mp3s):
                print(f"  Pausing {args.pause:.1f}s before next MP3...")
                time.sleep(args.pause)

    print(f"\n{'═' * 52}")
    print(f"Done: {grand_tagged} tagged, {grand_skipped} skipped, {grand_errors} errors")
    if grand_errors:
        print(f"Check {LOG_FILE} for details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
