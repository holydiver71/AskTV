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
# They come from well-known show intros and sign-offs in the 1981 transcripts.
REFERENCE_SEGMENTS = [
    ("data/episodes/1978/FRS 1978-12-08.json", 2033.00, 2053.00),
    ("data/episodes/1978/FRS 1978-12-08.json", 3543.52, 3567.81),
    ("data/episodes/1979/FRS 1979-03-23.json", 4590.17, 4602.93),
    ("data/episodes/1979/FRS 1979-07-20.json", 2570.17, 2575.93),
    ("data/episodes/1980/FRS 1980-08-08.json", 23.05, 28.0),
    ("data/episodes/1980/FRS 1980-08-08.json", 6757.05, 6767.0),
    ("data/episodes/1981/FRS 1981-06-03.json", 7074.05, 7086.0),
    ("data/episodes/1982/FRS 1982-05-14.json", 1705.00, 1716.00),
    ("data/episodes/1982/FRS 1982-04-10.json", 3395.00, 3410.00)
]

AUDIO_DIRS = [
    Path("FRSAudio/128kbps/1978"),
    Path("FRSAudio/128kbps/1979"),
    Path("FRSAudio/128kbps/1980"),
    Path("FRSAudio/128kbps/1981"),
    Path("FRSAudio/128kbps/1982")
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


def extract_clip(mp3_path: Path, start_s: float, end_s: float, ref_name: str | None = None) -> np.ndarray:
    """Load an audio clip and return it as a float32 numpy array at 16 kHz."""
    audio = AudioSegment.from_mp3(str(mp3_path))
    clip = audio[int(start_s * 1000): int(end_s * 1000)]
    clip = clip.set_frame_rate(16000).set_channels(1)

    if ref_name is not None:
        REFS_DIR.mkdir(parents=True, exist_ok=True)
        clip.export(str(REFS_DIR / ref_name), format="wav")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        clip.export(tmp_path, format="wav")
        return preprocess_wav(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


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
        wav = extract_clip(mp3, start_s, end_s, ref_name=clip_name)
        embedding = np.asarray(encoder.embed_utterance(wav), dtype=np.float32)
        embeddings.append(embedding)
        print(f"    → embedding shape: {embedding.shape}, norm: {np.linalg.norm(embedding):.3f}")

    if not embeddings:
        print("ERROR: No reference clips extracted. Check your AUDIO_DIRS paths.")
        return

    mean_embedding = np.mean(embeddings, axis=0)
    np.save(OUTPUT_PATH, mean_embedding)
    print(f"\nSaved Tommy Vance embedding to {OUTPUT_PATH}")
    print(f"Built from {len(embeddings)} reference clips.")
    print("\nSpot-check — cosine similarities between each clip and the mean:")
    for index, embedding in enumerate(embeddings):
        similarity = cosine_similarity(embedding, mean_embedding)
        print(f"  Clip {index + 1}: {similarity:.4f}  (should be ≥ 0.80)")


if __name__ == "__main__":
    main()