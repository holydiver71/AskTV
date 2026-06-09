#!/usr/bin/env python3
"""Build a Tommy Vance voice embedding from known-good speech segments.

Reads JSON transcript files to find segments that are definitely Tommy talking,
extracts those moments from the matching MP3s, and produces an average voice
fingerprint saved to data/tommy_vance_embedding.npy.

Run once before diarise_transcripts.py:
    python scripts/build_tv_embedding.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav

# Each entry is (json_path, start_seconds, end_seconds)
# These are segments we are CERTAIN are Tommy Vance speaking.
# All new entries use show openings: "This is TV on the Radio, Thomas Vance..."
# which are unambiguously Tommy with no other voices or music.
REFERENCE_SEGMENTS = [
    # 1980
    ("data/episodes/1980/FRS 1980-08-08.json", 23.05, 28.00),       # "This is Thomas the Clown here..." — show opening
    ("data/episodes/1980/FRS 1980-12-05.json", 1390.15, 1415.15),   # "10.26, and now from 1970, Elton John" — dry link
    # 1981
    ("data/episodes/1981/FRS 1981-04-10.json", 4.18, 20.52),        # "This is TV on the Radio here, Thomas the Vance..." — show opening
    ("data/episodes/1981/FRS 1981-07-10.json", 1.07, 20.25),        # "This is National Radio 1. Well, hello there. This is TV on the Radio..." — show opening
    # 1982
    ("data/episodes/1982/FRS 1982-01-22.json", 1.17, 19.48),        # "This is TV on the radio here, Thomas the Vance..." — show opening
    ("data/episodes/1982/FRS 1982-05-07.json", 4815.59, 4840.59),   # "good luck and here's more gillan..." — show link
    ("data/episodes/1982/FRS 1982-06-18.json", 12.11, 28.45),       # "Hello there, this is TV on the Radio here, Thomas the Vance..." — show opening
    # 1983
    ("data/episodes/1983/FRS 1983-03-04.json", 12.62, 35.18),       # "This is TV on the Radio here, Thomas Vance, and welcome..." — show opening
    ("data/episodes/1983/FRS 1983-08-05.json", 2712.51, 2737.51),   # "That's the artist that man has always, always been" — post-track
    # 1984
    ("data/episodes/1984/FRS 1984-05-18.json", 1899.44, 1924.44),   # "And that is exactly how it was on BBC television..." — archive link
    ("data/episodes/1984/FRS 1984-10-19.json", 9.02, 33.02),        # "This is TV on the Radio, here's Thomas Vance, and welcome..." — show opening
    # 1985
    ("data/episodes/1985/FRS 1985-01-18.json", 1.71, 34.36),        # "This is TV on the radio, Thomas the Vance here, the music vendor..." — show opening
    ("data/episodes/1985/FRS 1985-11-22.json", 9.16, 33.45),        # "This is TV on the Radio, Thomas Vance here, the music vendor..." — show opening
    # 1986
    ("data/episodes/1986/FRS 1986-01-24.json", 14.74, 36.36),       # "This is TV on the Radio, Thomas Vance here, the music vendor..." — show opening
    ("data/episodes/1986/FRS 1986-09-12.json", 9.52, 39.18),        # "Hello there, this is TV on the Radio, Thomas Vance..." — show opening
    ("data/episodes/1986/FRS 1986-10-10.json", 7.10, 29.71),        # "Oh hello there, this is TV on the Radio, Thomas Vance..." — show opening
]

CHUNK_SECONDS = 10.0   # clips longer than this are split into chunks of this length
CHUNK_MIN_SECONDS = 4.0  # discard tail chunks shorter than this

AUDIO_DIRS = [
    Path("FRSAudio/128kbps/1980"),
    Path("FRSAudio/128kbps/1981"),
    Path("FRSAudio/128kbps/1982"),
    Path("FRSAudio/128kbps/1983"),
    Path("FRSAudio/128kbps/1984"),
    Path("FRSAudio/128kbps/1985"),
    Path("FRSAudio/128kbps/1986"),
]

OUTPUT_PATH = Path("data/tommy_vance_embedding.npy")
REFS_DIR = Path("data/references")


def find_mp3(date: str) -> Path | None:
    """Find the MP3 for a given date string (YYYY-MM-DD)."""
    for audio_dir in AUDIO_DIRS:
        for mp3 in audio_dir.glob("*.mp3"):
            if date in mp3.name:
                return mp3
    return None


def _wav_from_segment(segment: AudioSegment) -> np.ndarray:
    """Export a pydub AudioSegment to a temp WAV and return preprocessed array."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        segment.export(tmp_path, format="wav")
        return preprocess_wav(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def extract_chunks(
    mp3_path: Path,
    start_s: float,
    end_s: float,
    ref_name: str | None = None,
) -> list[np.ndarray]:
    """Extract audio and return one preprocessed array per chunk.

    Clips shorter than CHUNK_SECONDS are returned as a single chunk.
    Longer clips are split into CHUNK_SECONDS-length pieces; any tail
    shorter than CHUNK_MIN_SECONDS is discarded.
    """
    audio = AudioSegment.from_mp3(str(mp3_path))
    clip = audio[int(start_s * 1000): int(end_s * 1000)]
    clip = clip.set_frame_rate(16000).set_channels(1)

    duration_s = len(clip) / 1000.0

    if ref_name is not None:
        REFS_DIR.mkdir(parents=True, exist_ok=True)
        clip.export(str(REFS_DIR / ref_name), format="wav")

    if duration_s <= CHUNK_SECONDS:
        return [_wav_from_segment(clip)]

    chunks = []
    chunk_ms = int(CHUNK_SECONDS * 1000)
    offset_ms = 0
    while offset_ms < len(clip):
        piece = clip[offset_ms: offset_ms + chunk_ms]
        if len(piece) / 1000.0 >= CHUNK_MIN_SECONDS:
            chunks.append(_wav_from_segment(piece))
        offset_ms += chunk_ms

    return chunks


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity between two 1-D numpy arrays."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> None:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    encoder = VoiceEncoder()
    embeddings: list[np.ndarray] = []

    for json_path_str, start_s, end_s in REFERENCE_SEGMENTS:
        json_path = Path(json_path_str)
        date = json_path.stem.replace("FRS ", "")
        mp3 = find_mp3(date)
        if mp3 is None:
            print(f"  WARNING: No MP3 found for {date} — skipping this reference")
            continue

        duration = end_s - start_s
        print(f"  Extracting {date} @ {start_s:.1f}s–{end_s:.1f}s ({duration:.1f}s)...")
        clip_name = f"{date}_{start_s:.2f}_{end_s:.2f}.wav"
        chunks = extract_chunks(mp3, start_s, end_s, ref_name=clip_name)
        for chunk_idx, wav in enumerate(chunks):
            embedding = np.asarray(encoder.embed_utterance(wav), dtype=np.float32)
            embeddings.append(embedding)
        print(f"    → {len(chunks)} chunk(s), {len(embeddings)} embeddings so far")

    if not embeddings:
        print("ERROR: No reference clips extracted. Check your AUDIO_DIRS paths.")
        return

    mean_embedding = np.mean(embeddings, axis=0)
    np.save(OUTPUT_PATH, mean_embedding)
    print(f"\nSaved Tommy Vance embedding to {OUTPUT_PATH}")
    print(f"Built from {len(embeddings)} embeddings across {len(REFERENCE_SEGMENTS)} reference segments.")
    print("\nSpot-check — cosine similarities between each embedding and the mean:")
    for index, embedding in enumerate(embeddings):
        similarity = cosine_similarity(embedding, mean_embedding)
        print(f"  Embedding {index + 1:>2}: {similarity:.4f}  (should be ≥ 0.80)")


if __name__ == "__main__":
    main()