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
    # 1978
    ("data/episodes/1978/FRS 1978-12-08.json", 2033.00, 2053.00),   # "I've got a nice card here..." — clean studio
    ("data/episodes/1978/FRS 1978-12-01.json", 4816.60, 4841.60),   # "Beautiful track by Joan Armatrading..." — post-track link
    # 1979
    ("data/episodes/1979/FRS 1979-03-23.json", 4590.17, 4602.93),   # Friday Night Connection announcement
    ("data/episodes/1979/FRS 1979-07-20.json", 2570.17, 2575.93),   # King Crimson BBC sessions mention
    ("data/episodes/1979/FRS 1979-07-06.json", 1662.88, 1687.88),   # "Now, come on, Paul..." — show intro
    ("data/episodes/1979/FRS 1979-11-02.json", 1655.11, 1680.11),   # "another oldie the voice of paul mccartney..." — commentary
    # 1980
    ("data/episodes/1980/FRS 1980-08-08.json", 23.05, 28.00),       # "This is Thomas the Clown here..." — show opening
    ("data/episodes/1980/FRS 1980-09-19.json", 4435.38, 4460.38),   # "That's the Friday Night Connection..." — dry link
    ("data/episodes/1980/FRS 1980-12-05.json", 1390.15, 1415.15),   # "10.26, and now from 1970, Elton John" — dry link
    # 1981
    ("data/episodes/1981/FRS 1981-02-06.json", 1917.17, 1942.17),   # "Recorded in the BBC studios on the 17th..." — post-track
    # 1982
    ("data/episodes/1982/FRS 1982-05-14.json", 1705.00, 1716.00),   # "I hope you've enjoyed the Status Quo concert..." — dry link
    ("data/episodes/1982/FRS 1982-08-27.json", 3796.14, 3821.14),   # "The caucus clowns of the fabulous Fandango Hotel..." — band intro
]

AUDIO_DIRS = [
    Path("FRSAudio/128kbps/1978"),
    Path("FRSAudio/128kbps/1979"),
    Path("FRSAudio/128kbps/1980"),
    Path("FRSAudio/128kbps/1981"),
    Path("FRSAudio/128kbps/1982"),
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