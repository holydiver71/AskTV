#!/usr/bin/env python3
"""Build a Tommy Vance voice embedding from known-good speech segments.

Two source types are merged:
  REFERENCE_WAVS     — pre-validated WAV files in data/references/, loaded directly.
  REFERENCE_SEGMENTS — (json_path, start_s, end_s) tuples, extracted from MP3s at runtime.

Clips longer than CHUNK_SECONDS are split into non-overlapping chunks so that
each 10-second window contributes its own d-vector to the mean. Chunks per
segment are capped at MAX_CHUNKS_PER_SEGMENT to prevent any single long clip
from dominating the mean embedding.

Run once before diarise_transcripts.py:
    python scripts/build_tv_embedding.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav

# ---------------------------------------------------------------------------
# Pre-validated WAV clips — loaded directly, no MP3 required.
# Filenames encode source: YYYY-MM-DD_start_end.wav
# ---------------------------------------------------------------------------
REFERENCE_WAVS = [
    Path("data/references/1978-12-08_2033.00_2053.00.wav"),
    Path("data/references/1978-12-08_3543.52_3567.81.wav"),
    Path("data/references/1979-03-23_4590.17_4602.93.wav"),
    Path("data/references/1980-08-08_6757.05_6767.00.wav"),
    Path("data/references/1982-05-14_1705.00_1716.00.wav"),
]

# ---------------------------------------------------------------------------
# MP3-based segments — (json_path, start_seconds, end_seconds)
# ---------------------------------------------------------------------------
REFERENCE_SEGMENTS = [
    # 1980
    ("data/episodes/1980/FRS 1980-08-08.json", 23.05, 28.00),       # "This is Thomas the Clown here..." — show opening
    ("data/episodes/1980/FRS 1980-12-05.json", 1390.15, 1396.0),    # "10.26, and now from 1970, Elton John" — trimmed: song starts at ~1396s
    # 1981
    ("data/episodes/1981/FRS 1981-04-10.json", 4.18, 20.52),        # "This is TV on the Radio here, Thomas the Vance..." — show opening
    ("data/episodes/1981/FRS 1981-07-10.json", 1.07, 20.25),        # "This is National Radio 1. Well, hello there..." — show opening
    # 1982
    ("data/episodes/1982/FRS 1982-01-22.json", 1.17, 19.48),        # "This is TV on the radio here, Thomas the Vance..." — show opening
    ("data/episodes/1982/FRS 1982-05-07.json", 4815.59, 4825.0),    # "good luck and here's more gillan..." — trimmed to first chunk before music fades in
    ("data/episodes/1982/FRS 1982-06-18.json", 12.11, 28.45),       # "Hello there, this is TV on the Radio here, Thomas the Vance..." — show opening
    # 1983
    ("data/episodes/1983/FRS 1983-01-21.json", 4685.0, 4693.0),     # "Friday Night Connection, Friday Rock Show, BBC Radio 1..." — address link
    ("data/episodes/1983/FRS 1983-03-04.json", 12.62, 23.0),         # "This is TV on the Radio here, Thomas Vance, and welcome..." — trimmed to one clean chunk
    ("data/episodes/1983/FRS 1983-03-25.json", 7005.0, 7019.0),     # "Next week on the Friday Rock Show, you can hear part two..." — sign-off link
    # 1984
    ("data/episodes/1984/FRS 1984-04-13.json", 24.0, 44.0),         # "I hope you're all right... during the next couple of hours..." — show opening
    ("data/episodes/1984/FRS 1984-05-18.json", 1899.44, 1924.44),   # "And that is exactly how it was on BBC television..." — archive link
    ("data/episodes/1984/FRS 1984-10-19.json", 9.02, 33.02),        # "This is TV on the Radio, here's Thomas Vance, and welcome..." — show opening
    # 1985
    ("data/episodes/1985/FRS 1985-01-18.json", 1.71, 12.0),          # "This is TV on the radio, Thomas the Vance here..." — trimmed to first clean chunk
    ("data/episodes/1985/FRS 1985-06-14.json", 530.0, 578.0),       # "A repeat session by them tonight. Before that, you heard..." — dry link
    ("data/episodes/1985/FRS 1985-06-14.json", 1132.0, 1143.0),     # "I'm going to listen to it again tonight..." — anecdote
    ("data/episodes/1985/FRS 1985-11-08.json", 4840.0, 4870.0),     # "here on the Friday Rock Show from BBC Radio 1..." — trimmed to 3 chunks, 4th+ had music bed
    # 1986
    ("data/episodes/1986/FRS 1986-01-24.json", 14.74, 25.0),         # "This is TV on the Radio, Thomas Vance here..." — trimmed to first clean chunk
    ("data/episodes/1986/FRS 1986-04-04.json", 730.0, 1200.0),      # "Now, Judas Priest, of course, come from Wolverhampton..." — extended link (capped)
    ("data/episodes/1986/FRS 1986-04-04.json", 5407.0, 5463.0),     # "Before that you heard The Alliance..." — post-track link
    ("data/episodes/1986/FRS 1986-09-12.json", 9.52, 39.18),        # "Hello there, this is TV on the Radio, Thomas Vance..." — show opening
    ("data/episodes/1986/FRS 1986-10-10.json", 7.10, 29.71),        # "Oh hello there, this is TV on the Radio, Thomas Vance..." — show opening
]

CHUNK_SECONDS = 10.0        # clips longer than this are split into this-length chunks
CHUNK_MIN_SECONDS = 6.0     # discard tail chunks shorter than this (raised from 4s to drop unreliable short tails)
MAX_CHUNKS_PER_SEGMENT = 5  # cap embeddings per segment so no single clip dominates the mean

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

WAV_SAMPLE_RATE = 16000  # resemblyzer operates at 16 kHz


def find_mp3(date: str) -> Path | None:
    for audio_dir in AUDIO_DIRS:
        for mp3 in audio_dir.glob("*.mp3"):
            if date in mp3.name:
                return mp3
    return None


def _wav_from_segment(segment: AudioSegment) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        segment.export(tmp_path, format="wav")
        return preprocess_wav(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _chunk_array(wav: np.ndarray) -> list[np.ndarray]:
    """Split a preprocessed wav array into CHUNK_SECONDS-length pieces."""
    samples_per_chunk = int(CHUNK_SECONDS * WAV_SAMPLE_RATE)
    min_samples = int(CHUNK_MIN_SECONDS * WAV_SAMPLE_RATE)
    if len(wav) <= samples_per_chunk:
        return [wav]
    chunks = []
    for offset in range(0, len(wav), samples_per_chunk):
        piece = wav[offset: offset + samples_per_chunk]
        if len(piece) >= min_samples:
            chunks.append(piece)
    return chunks[:MAX_CHUNKS_PER_SEGMENT]


def extract_chunks_from_mp3(
    mp3_path: Path,
    start_s: float,
    end_s: float,
    ref_name: str | None = None,
) -> list[np.ndarray]:
    """Extract a window from an MP3 and return chunked preprocessed arrays."""
    audio = AudioSegment.from_mp3(str(mp3_path))
    clip = audio[int(start_s * 1000): int(end_s * 1000)]
    clip = clip.set_frame_rate(WAV_SAMPLE_RATE).set_channels(1)

    if ref_name is not None:
        REFS_DIR.mkdir(parents=True, exist_ok=True)
        clip.export(str(REFS_DIR / ref_name), format="wav")

    wav = _wav_from_segment(clip)
    return _chunk_array(wav)


def extract_chunks_from_wav(wav_path: Path) -> list[np.ndarray]:
    """Load a pre-extracted WAV file and return chunked preprocessed arrays."""
    wav = preprocess_wav(wav_path)
    return _chunk_array(wav)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> None:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    encoder = VoiceEncoder()
    embeddings: list[np.ndarray] = []
    labels: list[str] = []

    # --- WAV sources ---
    print("Loading pre-validated WAV references...")
    for wav_path in REFERENCE_WAVS:
        if not wav_path.exists():
            print(f"  WARNING: {wav_path} not found — skipping")
            continue
        chunks = extract_chunks_from_wav(wav_path)
        for chunk_idx, wav in enumerate(chunks):
            embeddings.append(np.asarray(encoder.embed_utterance(wav), dtype=np.float32))
            labels.append(f"{wav_path.stem} chunk {chunk_idx + 1}/{len(chunks)}")
        print(f"  {wav_path.name}  → {len(chunks)} chunk(s)")

    # --- MP3-based segments ---
    print("\nExtracting MP3-based segments...")
    for json_path_str, start_s, end_s in REFERENCE_SEGMENTS:
        json_path = Path(json_path_str)
        date = json_path.stem.replace("FRS ", "")
        mp3 = find_mp3(date)
        if mp3 is None:
            print(f"  WARNING: No MP3 found for {date} — skipping")
            continue

        duration = end_s - start_s
        print(f"  {date} @ {start_s:.1f}–{end_s:.1f}s ({duration:.0f}s)...")
        clip_name = f"{date}_{start_s:.2f}_{end_s:.2f}.wav"
        chunks = extract_chunks_from_mp3(mp3, start_s, end_s, ref_name=clip_name)
        for chunk_idx, wav in enumerate(chunks):
            embeddings.append(np.asarray(encoder.embed_utterance(wav), dtype=np.float32))
            offset = start_s + chunk_idx * CHUNK_SECONDS
            labels.append(f"{date} {offset:.0f}–{min(offset + CHUNK_SECONDS, end_s):.0f}s")
        print(f"    → {len(chunks)} chunk(s), {len(embeddings)} embeddings total")

    if not embeddings:
        print("ERROR: No embeddings produced. Check AUDIO_DIRS paths and REFERENCE_WAVS.")
        return

    mean_embedding = np.mean(embeddings, axis=0)
    np.save(OUTPUT_PATH, mean_embedding)
    print(f"\nSaved Tommy Vance embedding to {OUTPUT_PATH}")
    print(f"Built from {len(embeddings)} embeddings ({len(REFERENCE_WAVS)} WAV sources + {len(REFERENCE_SEGMENTS)} MP3 segments).")
    print("\nSpot-check — cosine similarities between each embedding and the mean:")
    for index, (embedding, label) in enumerate(zip(embeddings, labels)):
        similarity = cosine_similarity(embedding, mean_embedding)
        flag = "  *** BELOW 0.80 ***" if similarity < 0.80 else ""
        print(f"  {index + 1:>2}: {similarity:.4f}  {label}{flag}")


if __name__ == "__main__":
    main()
