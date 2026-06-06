#!/usr/bin/env python3
"""Tag transcript segments with "source": "TV" or "source": "uncertain".

Runs speaker diarisation on each episode MP3, identifies which speaker
cluster matches Tommy Vance's saved voice embedding, then writes the
"source" field back to each transcript segment in the JSON file.

Run from the workspace root:
    python scripts/diarise_transcripts.py --year 1981
    python scripts/diarise_transcripts.py --mp3 "FRSAudio/128kbps/1981/FRS 1981-04-10_128kps.mp3"

Idempotent: re-running overwrites existing "source" fields (use --retag to force).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from dotenv import load_dotenv
from huggingface_hub.utils import GatedRepoError
from pyannote.audio import Pipeline
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav

load_dotenv()

TV_EMBEDDING_PATH = Path("data/tommy_vance_embedding.npy")
LOG_FILE = Path("logs/diarisation_errors.log")
TV_SIMILARITY_THRESHOLD = 0.65
TV_SECONDARY_THRESHOLD = 0.76  # clusters above this are also tagged TV (TV-over-music)
MAX_CLIP_FOR_EMBEDDING_SECS = 45.0
MIN_OVERLAP_FRACTION = 0.50

STOP_REQUESTED = False


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\nInterrupt received — finishing current episode then stopping.")


def log_error(message: str) -> None:
    """Append a timestamped error line to the log file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {message}\n")
    print(f"  ERROR: {message}")


def atomic_write(path: Path, data: dict) -> None:
    """Write JSON to a .tmp file then rename — safe against partial writes."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def find_date_in_name(name: str) -> str | None:
    """Extract YYYY-MM-DD from a filename."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def cosine_similarity(a: np.ndarray | tuple | list, b: np.ndarray | tuple | list) -> float:
    """Return cosine similarity between two 1-D numpy arrays (range -1 to 1)."""
    a = np.asarray(a)
    b = np.asarray(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def resolve_device(requested: str) -> torch.device:
    """Resolve the runtime device for pyannote and resemblyzer."""
    if requested == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    return torch.device(requested)


def overlap_seconds(seg_start: float, seg_end: float, turn_start: float, turn_end: float) -> float:
    """How many seconds do two time intervals share?"""
    start = max(seg_start, turn_start)
    end = min(seg_end, turn_end)
    return max(0.0, end - start)


def load_tv_embedding(path: Path = TV_EMBEDDING_PATH) -> np.ndarray:
    """Load the pre-built Tommy Vance voice fingerprint from disk.

    Raises FileNotFoundError with a helpful message if missing.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Tommy Vance embedding not found at {path}.\n"
            "Run 'python scripts/build_tv_embedding.py' first."
        )
    embedding = np.load(path)
    print(f"Loaded TV embedding from {path}  shape={embedding.shape}")
    return embedding


def extract_speaker_clip(
    mp3_path: Path,
    turns: list[tuple[float, float]],
    max_secs: float = MAX_CLIP_FOR_EMBEDDING_SECS,
) -> np.ndarray | None:
    """Concatenate up to max_secs of audio from the given speaker turns."""
    audio = AudioSegment.from_mp3(str(mp3_path))
    collected = AudioSegment.empty()

    for start_s, end_s in turns:
        if len(collected) / 1000.0 >= max_secs:
            break

        remaining_ms = int(max_secs * 1000 - len(collected))
        if remaining_ms <= 0:
            break

        clip = audio[int(start_s * 1000) : int(end_s * 1000)]
        if len(clip) > remaining_ms:
            clip = clip[:remaining_ms]
        collected += clip

    if len(collected) < 500:
        return None

    collected = collected.set_frame_rate(16000).set_channels(1)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        collected.export(str(tmp_path), format="wav")
        return preprocess_wav(str(tmp_path))
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def run_diarisation(pipeline: Pipeline, mp3_path: Path) -> dict[str, list[tuple[float, float]]]:
    """Run speaker diarisation on the MP3."""
    print("  Running speaker diarisation (this takes several minutes on CPU)...")
    diarisation = pipeline(str(mp3_path))

    speakers: dict[str, list[tuple[float, float]]] = {}
    for turn, _, speaker in diarisation.itertracks(yield_label=True):
        speakers.setdefault(speaker, []).append((turn.start, turn.end))

    print(f"  Diarisation complete: {len(speakers)} speaker cluster(s) found: {list(speakers.keys())}")
    return speakers


def identify_tv_speaker(
    mp3_path: Path,
    speakers: dict[str, list[tuple[float, float]]],
    tv_embedding: np.ndarray,
    encoder: VoiceEncoder,
    similarity_threshold: float = TV_SIMILARITY_THRESHOLD,
    secondary_threshold: float = TV_SECONDARY_THRESHOLD,
) -> list[str]:
    """Find all speaker clusters that match Tommy Vance's voice.

    Returns a list: first entry is the best match, additional entries are
    clusters above secondary_threshold (e.g. TV speaking over background music).
    Returns an empty list if no cluster meets similarity_threshold.
    """
    print(f"  Fingerprinting {len(speakers)} speaker cluster(s) for TV match...")
    best_speaker = None
    best_similarity = -1.0
    scores: dict[str, float] = {}

    for speaker, turns in speakers.items():
        print(f"  Fingerprinting cluster {speaker} ({len(turns)} turns)...")
        wav = extract_speaker_clip(mp3_path, turns)
        if wav is None:
            print("    → Skipped (not enough audio)")
            continue

        embedding = encoder.embed_utterance(wav)
        similarity = cosine_similarity(embedding, tv_embedding)
        scores[speaker] = similarity
        print(f"    → Similarity to Tommy Vance: {similarity:.4f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_speaker = speaker

    if best_speaker is None or best_similarity < similarity_threshold:
        print(
            f"  WARNING: Best match ({best_speaker}) only scored {best_similarity:.4f} "
            f"— below threshold {similarity_threshold}. Flagging for review."
        )
        return []

    # Collect additional clusters that are likely TV (e.g. TV over background music)
    tv_speakers = [best_speaker]
    for speaker, sim in scores.items():
        if speaker != best_speaker and sim >= secondary_threshold:
            tv_speakers.append(speaker)
            print(f"  Also tagging {speaker} as TV (similarity={sim:.4f} ≥ secondary threshold)")

    print(f"  Tommy Vance identified as: {best_speaker}  (similarity={best_similarity:.4f})")
    if len(tv_speakers) > 1:
        print(f"  TV speaker clusters: {tv_speakers}")
    return tv_speakers


def tag_segments(
    transcript: list[dict],
    speakers: dict[str, list[tuple[float, float]]],
    tv_speakers: list[str] | None,
) -> int:
    """Write "source" field onto each non-music transcript segment."""
    tv_speaker_set = set(tv_speakers) if tv_speakers else set()
    tv_count = 0
    speech_count = sum(1 for seg in transcript if seg.get("type") != "music")
    tagged_count = 0

    for seg in transcript:
        if seg.get("type") == "music":
            continue

        tagged_count += 1
        if tagged_count == 1 or tagged_count == speech_count or tagged_count % 25 == 0:
            print(f"  Tagging segment {tagged_count}/{speech_count}...")

        seg_start = float(seg["start"])
        seg_end = float(seg["end"])
        seg_duration = seg_end - seg_start

        if seg_duration <= 0:
            seg["source"] = "other"
            continue

        best_speaker = None
        best_overlap = 0.0

        for speaker, turns in speakers.items():
            total_overlap = sum(
                overlap_seconds(seg_start, seg_end, turn_start, turn_end)
                for turn_start, turn_end in turns
            )
            if total_overlap > best_overlap:
                best_overlap = total_overlap
                best_speaker = speaker

        if best_speaker is not None and (best_overlap / seg_duration) >= MIN_OVERLAP_FRACTION:
            seg["source"] = "TV" if best_speaker in tv_speaker_set else "uncertain"
        else:
            seg["source"] = "uncertain"

        if seg["source"] == "TV":
            tv_count += 1

    return tv_count


def process_episode(
    pipeline: Pipeline,
    encoder: VoiceEncoder,
    tv_embedding: np.ndarray,
    mp3_path: Path,
    json_path: Path,
    retag: bool = False,
    similarity_threshold: float = TV_SIMILARITY_THRESHOLD,
) -> str:
    """Process one episode: diarise, identify TV, tag segments, write back."""
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
    print(f"  Transcript loaded: {len(transcript)} total segments, {len(speech_segments)} speech segments")
    already_tagged = any("source" in s for s in speech_segments)
    if already_tagged and not retag:
        print("  Already tagged — skipping. Use --retag to overwrite.")
        return "skipped"

    try:
        print("  Step 1/4: diarisation")
        speakers = run_diarisation(pipeline, mp3_path)
    except Exception as exc:
        log_error(f"{mp3_path.name}: Diarisation failed: {exc}")
        return "error"

    if not speakers:
        log_error(f"{mp3_path.name}: No speakers found by pyannote")
        return "error"

    print("  Step 2/4: speaker fingerprinting")
    tv_speakers = identify_tv_speaker(
        mp3_path,
        speakers,
        tv_embedding,
        encoder,
        similarity_threshold=similarity_threshold,
    )
    if not tv_speakers:
        log_error(
            f"{mp3_path.name}: Could not identify Tommy Vance with confidence — all segments will be tagged 'uncertain'"
        )

    print("  Step 3/4: transcript tagging")
    tv_count = tag_segments(transcript, speakers, tv_speakers)
    total_speech = len(speech_segments)
    uncertain_count = total_speech - tv_count

    print(f"  Tagged {tv_count}/{total_speech} speech segments as 'TV' ({uncertain_count} as 'uncertain')")

    print("  Step 4/4: writing JSON")
    data["transcript"] = transcript
    atomic_write(json_path, data)
    print(f"  Saved → {json_path.name}")
    return "tagged"


def main() -> int:
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(description="Tag transcript segments with source: TV or uncertain.")
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
        help=f"Cosine similarity threshold for TV identification (default: {TV_SIMILARITY_THRESHOLD})",
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
        help="Runtime device for diarisation and embeddings (default: auto)",
    )
    args = parser.parse_args()

    try:
        tv_embedding = load_tv_embedding(args.ref_embedding)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    hf_token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not hf_token:
        print("ERROR: HUGGINGFACE_TOKEN not set in .env")
        print("See Phase A2 in the plan for instructions.")
        return 1

    print("Loading pyannote speaker diarisation pipeline...")
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
    except GatedRepoError:
        print("ERROR: HuggingFace denied access to pyannote/speaker-diarization-community-1")
        print("Accept the model terms at https://huggingface.co/pyannote/speaker-diarization-community-1")
        print("Then re-run the script with the same HUGGINGFACE_TOKEN.")
        return 1
    device = resolve_device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        print("ERROR: --device cuda requested, but CUDA is not available on this machine.")
        print("Use --device cpu, or upgrade the NVIDIA driver/CUDA stack and try again.")
        return 1
    pipeline.to(device)
    print("Loading resemblyzer voice encoder...")
    encoder = VoiceEncoder(device=device)
    print("Models ready.\n")

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
            pipeline,
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
                pipeline,
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