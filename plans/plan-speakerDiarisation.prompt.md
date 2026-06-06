# Plan: Speaker Diarisation — Detailed Step-by-Step

**Goal**: Add a `"source"` field to every non-music transcript segment.  
`"TV"` = Tommy Vance speaking. `"other"` = anyone/anything else.

**How it works (plain English)**:  
1. We extract short audio clips of Tommy's voice from known timestamps in existing transcripts — these become our "reference" samples.  
2. A library called `resemblyzer` turns any audio clip into a compact list of 256 numbers (a "voice fingerprint" or "embedding") that represents what that voice *sounds* like.  
3. We compute Tommy's average fingerprint from all the reference clips and save it to disk.  
4. For each episode, a second library called `pyannote.audio` listens to the whole MP3 and splits it into turns like: *"SPEAKER_00 was talking from 4s to 20s, SPEAKER_01 from 7163s to 7165s"* etc. — it does not know names, just clusters voices together.  
5. We fingerprint each discovered speaker cluster, compare against Tommy's saved fingerprint, and whichever cluster scores highest (and clears a minimum threshold) gets labelled `"TV"`. All others get `"other"`.  
6. We match those speaker turns back against the Whisper transcript timestamps and write the `"source"` field.

**Prerequisites** (must be done before starting):
- Transcription complete for the year(s) you want to tag
- `clean_transcripts.py` run so `[Music]` placeholders are in place

---

## Phase A — Environment Setup

- [X] Step A1 — Install the three new libraries

Run from the workspace root with the venv active:

```
source .venv/bin/activate
pip install resemblyzer pyannote.audio pydub
```

**What each one does:**
- `resemblyzer` — voice fingerprinting (no account needed)
- `pyannote.audio` — speaker diarisation (needs a free HuggingFace account — see A2)
- `pydub` — audio slicing (reads/writes WAV/MP3 clips)

After installing, freeze them into `requirements.txt`:
```
pip freeze | grep -E "resemblyzer|pyannote|pydub" >> requirements.txt
```

- [X] Step A2 — Get a free HuggingFace token

`pyannote.audio` uses a pretrained model hosted on HuggingFace. You need a free account and to accept two model licences.

1. Go to https://huggingface.co and create a free account.
2. Accept the licence at https://huggingface.co/pyannote/speaker-diarization-3.1  
3. Accept the licence at https://huggingface.co/pyannote/segmentation-3.0  
4. Go to https://huggingface.co/settings/tokens → click **New token** → name it "FRS" → select **Read** access → copy the token.
5. Open `.env` in the workspace root and add:
   ```
   HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
   ```

- [X] Step A3 — Add the token to the env validator

Open `scripts/validate_env.py`. Find the `checks` list (around line 12). Add one more entry at the end of that list:

```python
("HUGGINGFACE_TOKEN", "HuggingFace read token for pyannote.audio models"),
```

Run `python scripts/validate_env.py` — it should now pass.

---

## Phase B — Build the Tommy Vance Voice Profile

**Goal**: Produce `data/tommy_vance_embedding.npy` — a saved voice fingerprint.

- [X] Step B1 — Create a helper script: `scripts/build_tv_embedding.py`

This script does three things:
1. Reads a list of "known Tommy Vance" transcript segments from existing JSON files
2. Extracts short WAV clips from the matching MP3s using pydub
3. Runs each clip through resemblyzer and averages the results

**Create the file `scripts/build_tv_embedding.py`** with this structure:

```python
#!/usr/bin/env python3
"""Build a Tommy Vance voice embedding from known-good speech segments.

Reads JSON transcript files to find segments that are definitely Tommy talking,
extracts those moments from the matching MP3, and produces an average voice
fingerprint saved to data/tommy_vance_embedding.npy.

Run once before diarise_transcripts.py:
    python scripts/build_tv_embedding.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav
import soundfile as sf
import tempfile

# ── Configuration ────────────────────────────────────────────────────────────

# Each entry is (json_path, start_seconds, end_seconds)
# These are segments we are CERTAIN are Tommy Vance speaking.
# They come from well-known show intros and sign-offs in the 1981 transcripts.
# Add more from other years if you like — more variety = better fingerprint.
REFERENCE_SEGMENTS = [
    # 1981-04-10: show intro
    ("data/episodes/1981/FRS 1981-04-10.json", 4.18, 20.52),
    ("data/episodes/1981/FRS 1981-04-10.json", 20.52, 33.81),
    # 1981-04-10: sign-off
    ("data/episodes/1981/FRS 1981-04-10.json", 7151.17, 7153.93),
    ("data/episodes/1981/FRS 1981-04-10.json", 7171.05, 7173.91),
    # Add more from other episodes here as desired
]

AUDIO_DIRS = [
    Path("FRSAudio/128kbps/1980"),
    Path("FRSAudio/128kbps/1981"),
]

OUTPUT_PATH = Path("data/tommy_vance_embedding.npy")
REFS_DIR = Path("data/references")  # optional: save the WAV clips for inspection


def find_mp3(date: str) -> Path | None:
    """Find the MP3 for a given date string (YYYY-MM-DD)."""
    for audio_dir in AUDIO_DIRS:
        for mp3 in audio_dir.glob("*.mp3"):
            if date in mp3.name:
                return mp3
    return None


def extract_clip(mp3_path: Path, start_s: float, end_s: float) -> np.ndarray:
    """Load an audio clip and return it as a float32 numpy array at 16 kHz."""
    audio = AudioSegment.from_mp3(str(mp3_path))
    clip = audio[int(start_s * 1000): int(end_s * 1000)]
    # resemblyzer needs mono 16 kHz WAV in a temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        clip = clip.set_frame_rate(16000).set_channels(1)
        clip.export(tmp.name, format="wav")
        wav = preprocess_wav(tmp.name)
    return wav


def main() -> None:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    encoder = VoiceEncoder()
    embeddings = []

    for json_path_str, start_s, end_s in REFERENCE_SEGMENTS:
        json_path = Path(json_path_str)
        # Extract date from the JSON filename
        date = json_path.stem.replace("FRS ", "")   # "YYYY-MM-DD"
        mp3 = find_mp3(date)
        if mp3 is None:
            print(f"  WARNING: No MP3 found for {date} — skipping this reference")
            continue

        duration = end_s - start_s
        print(f"  Extracting {date} @ {start_s:.1f}s–{end_s:.1f}s ({duration:.1f}s)...")
        wav = extract_clip(mp3, start_s, end_s)
        embedding = encoder.embed_utterance(wav)
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
    for i, emb in enumerate(embeddings):
        sim = np.dot(emb, mean_embedding) / (np.linalg.norm(emb) * np.linalg.norm(mean_embedding))
        print(f"  Clip {i + 1}: {sim:.4f}  (should be ≥ 0.80)")


if __name__ == "__main__":
    main()
```

**Run it:**
```
python scripts/build_tv_embedding.py
```

**What success looks like:**
- Prints similarity scores — they should all be **≥ 0.80** (i.e. 0.80 or higher). If any are below 0.75, that clip is problematic — check that the MP3 is present and that the timestamp range is correct.
- Creates `data/tommy_vance_embedding.npy`

**If the MP3s for 1981 aren't downloaded yet**, add reference segments from a year that does have MP3s (e.g. 1980), using the same pattern. Check `data/episodes/1980/` for JSON files with good intro segments — look for `"text"` starting with "Well, hello there" or "This is Tommy Vance".

---

## Phase C — Write the Main Diarisation Script

Create `scripts/diarise_transcripts.py`. Build it in the order shown below — each section is self-contained and testable.

- [X] Step C1 — Boilerplate, imports, and constants

```python
#!/usr/bin/env python3
"""Tag transcript segments with "source": "TV" or "source": "other".

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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from pyannote.audio import Pipeline
from pydub import AudioSegment
from resemblyzer import VoiceEncoder, preprocess_wav

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
TV_EMBEDDING_PATH = Path("data/tommy_vance_embedding.npy")
LOG_FILE = Path("logs/diarisation_errors.log")

# ── Tuning ───────────────────────────────────────────────────────────────────
# Minimum cosine similarity for the best speaker cluster to be labelled "TV".
# If no cluster reaches this threshold the episode is flagged for manual review
# and all segments get "source": "other" as a safe fallback.
TV_SIMILARITY_THRESHOLD = 0.65

# How many seconds of audio to use when fingerprinting each speaker cluster.
# More is better but slower; 45 s is a good balance.
MAX_CLIP_FOR_EMBEDDING_SECS = 45.0

# Minimum fraction of a Whisper segment that must overlap a diarisation turn
# for the turn's speaker to be assigned. Segments below this stay "other".
MIN_OVERLAP_FRACTION = 0.50

# ── Globals ──────────────────────────────────────────────────────────────────
STOP_REQUESTED = False


def handle_sigint(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\nInterrupt received — finishing current episode then stopping.")
```

- [X] Step C2 — Utility functions (copy-paste these exactly)

These are small helper functions. Paste them directly below the globals section:

```python
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


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity between two 1-D numpy arrays (range −1 to 1)."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def overlap_seconds(seg_start: float, seg_end: float,
                    turn_start: float, turn_end: float) -> float:
    """How many seconds do two time intervals share?"""
    start = max(seg_start, turn_start)
    end = min(seg_end, turn_end)
    return max(0.0, end - start)
```

- [X] Step C3 — Loading Tommy's voice embedding

```python
def load_tv_embedding() -> np.ndarray:
    """Load the pre-built Tommy Vance voice fingerprint from disk.
    
    Raises FileNotFoundError with a helpful message if missing.
    """
    if not TV_EMBEDDING_PATH.exists():
        raise FileNotFoundError(
            f"Tommy Vance embedding not found at {TV_EMBEDDING_PATH}.\n"
            "Run 'python scripts/build_tv_embedding.py' first."
        )
    embedding = np.load(TV_EMBEDDING_PATH)
    print(f"Loaded TV embedding from {TV_EMBEDDING_PATH}  shape={embedding.shape}")
    return embedding
```

- [X] Step C4 — Extracting a speaker's audio clip for fingerprinting

```python
def extract_speaker_clip(mp3_path: Path, turns: list[tuple[float, float]],
                         max_secs: float = MAX_CLIP_FOR_EMBEDDING_SECS) -> np.ndarray | None:
    """Concatenate up to max_secs of audio from the given speaker turns.

    `turns` is a list of (start_seconds, end_seconds) pairs.
    Returns a float32 numpy array ready for resemblyzer, or None if no audio found.
    """
    audio = AudioSegment.from_mp3(str(mp3_path))
    collected = AudioSegment.empty()

    for start_s, end_s in turns:
        if len(collected) / 1000.0 >= max_secs:
            break
        clip = audio[int(start_s * 1000): int(end_s * 1000)]
        collected += clip

    if len(collected) < 500:   # less than 0.5 seconds — not usable
        return None

    # Convert to 16 kHz mono WAV for resemblyzer
    collected = collected.set_frame_rate(16000).set_channels(1)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        collected.export(tmp.name, format="wav")
        wav = preprocess_wav(tmp.name)
    return wav
```

- [X] Step C5 — Running pyannote diarisation on one episode

```python
def run_diarisation(pipeline: Pipeline, mp3_path: Path) -> dict[str, list[tuple[float, float]]]:
    """Run speaker diarisation on the MP3.

    Returns a dict mapping speaker label → list of (start_s, end_s) tuples.
    Example: {"SPEAKER_00": [(4.1, 20.5), (463.9, 470.0)], "SPEAKER_01": [(7163.8, 7165.5)]}
    """
    print("  Running speaker diarisation (this takes several minutes on CPU)...")
    # pyannote works directly with the file path
    diarisation = pipeline(str(mp3_path))

    speakers: dict[str, list[tuple[float, float]]] = {}
    for turn, _, speaker in diarisation.itertracks(yield_label=True):
        # turn.start and turn.end are in seconds (floats)
        speakers.setdefault(speaker, []).append((turn.start, turn.end))

    print(f"  Diarisation complete: {len(speakers)} speaker cluster(s) found: {list(speakers.keys())}")
    return speakers
```

- [X] Step C6 — Identifying which cluster is Tommy Vance

```python
def identify_tv_speaker(mp3_path: Path, speakers: dict[str, list[tuple[float, float]]],
                         tv_embedding: np.ndarray,
                         encoder: VoiceEncoder) -> str | None:
    """Find which speaker cluster most closely matches Tommy Vance's voice.

    Returns the speaker label (e.g. "SPEAKER_00") or None if similarity is
    too low (episode will need manual review).
    """
    best_speaker = None
    best_similarity = -1.0

    for speaker, turns in speakers.items():
        print(f"  Fingerprinting cluster {speaker} ({len(turns)} turns)...")
        wav = extract_speaker_clip(mp3_path, turns)
        if wav is None:
            print(f"    → Skipped (not enough audio)")
            continue
        embedding = encoder.embed_utterance(wav)
        similarity = cosine_similarity(embedding, tv_embedding)
        print(f"    → Similarity to Tommy Vance: {similarity:.4f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_speaker = speaker

    if best_similarity < TV_SIMILARITY_THRESHOLD:
        print(f"  WARNING: Best match ({best_speaker}) only scored {best_similarity:.4f} "
              f"— below threshold {TV_SIMILARITY_THRESHOLD}. Flagging for review.")
        return None  # don't assign TV label if we're not confident

    print(f"  Tommy Vance identified as: {best_speaker}  (similarity={best_similarity:.4f})")
    return best_speaker
```

- [X] Step C7 — Mapping speaker turns onto Whisper segments

```python
def tag_segments(transcript: list[dict],
                 speakers: dict[str, list[tuple[float, float]]],
                 tv_speaker: str | None) -> int:
    """Write "source" field onto each non-music transcript segment.

    Returns how many segments were tagged "TV".
    tv_speaker is the speaker label from pyannote (e.g. "SPEAKER_00"),
    or None if we couldn't identify Tommy with enough confidence.
    """
    tv_count = 0

    for seg in transcript:
        # Never touch music placeholder segments
        if seg.get("type") == "music":
            continue

        seg_start = float(seg["start"])
        seg_end = float(seg["end"])
        seg_duration = seg_end - seg_start

        if seg_duration <= 0:
            seg["source"] = "other"
            continue

        # For each speaker, total up how many seconds of their turns
        # overlap with this Whisper segment
        best_speaker = None
        best_overlap = 0.0

        for speaker, turns in speakers.items():
            total_overlap = sum(
                overlap_seconds(seg_start, seg_end, t_start, t_end)
                for t_start, t_end in turns
            )
            if total_overlap > best_overlap:
                best_overlap = total_overlap
                best_speaker = speaker

        # Only assign if the winning speaker covers at least MIN_OVERLAP_FRACTION
        # of the segment's duration
        if best_speaker is not None and (best_overlap / seg_duration) >= MIN_OVERLAP_FRACTION:
            seg["source"] = "TV" if best_speaker == tv_speaker else "other"
        else:
            seg["source"] = "other"  # ambiguous — safe fallback

        if seg["source"] == "TV":
            tv_count += 1

    return tv_count
```

- [X] Step C8 — Per-episode orchestration function

This ties all the steps together for one episode:

```python
def process_episode(pipeline: Pipeline, encoder: VoiceEncoder,
                    tv_embedding: np.ndarray,
                    mp3_path: Path, json_path: Path,
                    retag: bool = False) -> str:
    """Process one episode: diarise, identify TV, tag segments, write back.

    Returns a status string: "tagged", "skipped", or "error".
    """
    # Load the JSON
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

    # Skip if already tagged (unless --retag is set)
    speech_segments = [s for s in transcript if s.get("type") != "music"]
    already_tagged = any("source" in s for s in speech_segments)
    if already_tagged and not retag:
        print("  Already tagged — skipping. Use --retag to overwrite.")
        return "skipped"

    # Run diarisation
    try:
        speakers = run_diarisation(pipeline, mp3_path)
    except Exception as exc:
        log_error(f"{mp3_path.name}: Diarisation failed: {exc}")
        return "error"

    if not speakers:
        log_error(f"{mp3_path.name}: No speakers found by pyannote")
        return "error"

    # Identify Tommy
    tv_speaker = identify_tv_speaker(mp3_path, speakers, tv_embedding, encoder)
    if tv_speaker is None:
        log_error(f"{mp3_path.name}: Could not identify Tommy Vance with confidence "
                  f"— all segments will be tagged 'other'")
        # Still proceed: write "other" for everything rather than leaving untagged

    # Tag the segments
    tv_count = tag_segments(transcript, speakers, tv_speaker)
    total_speech = len(speech_segments)

    print(f"  Tagged {tv_count}/{total_speech} speech segments as 'TV' "
          f"({total_speech - tv_count} as 'other')")

    # Write back
    data["transcript"] = transcript
    atomic_write(json_path, data)
    print(f"  Saved → {json_path.name}")
    return "tagged"
```

- [X] Step C9 — main() function with argument parsing

```python
def main() -> int:
    signal.signal(signal.SIGINT, handle_sigint)

    parser = argparse.ArgumentParser(
        description="Tag transcript segments with source: TV or other."
    )
    parser.add_argument(
        "--year", "-y", nargs="+", default=["1981"], metavar="YYYY",
        help="One or more years to process (e.g. --year 1980 1981)"
    )
    parser.add_argument(
        "mp3", nargs="?",
        help="Optional: path to a single MP3 to process instead of a whole year"
    )
    parser.add_argument(
        "--retag", action="store_true",
        help="Overwrite existing 'source' fields (default: skip already-tagged episodes)"
    )
    parser.add_argument(
        "--threshold", type=float, default=TV_SIMILARITY_THRESHOLD,
        help=f"Cosine similarity threshold for TV identification (default: {TV_SIMILARITY_THRESHOLD})"
    )
    parser.add_argument(
        "--ref-embedding", type=Path, default=TV_EMBEDDING_PATH,
        help=f"Path to Tommy Vance embedding file (default: {TV_EMBEDDING_PATH})"
    )
    args = parser.parse_args()

    # Load TV embedding
    try:
        tv_embedding = np.load(args.ref_embedding)
    except FileNotFoundError:
        print(f"ERROR: Embedding not found at {args.ref_embedding}")
        print("Run 'python scripts/build_tv_embedding.py' first.")
        return 1

    # Load HuggingFace token
    hf_token = os.getenv("HUGGINGFACE_TOKEN", "").strip()
    if not hf_token:
        print("ERROR: HUGGINGFACE_TOKEN not set in .env")
        print("See Phase A2 in the plan for instructions.")
        return 1

    # Load models (once — they are slow to initialise)
    print("Loading pyannote speaker diarisation pipeline...")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    print("Loading resemblyzer voice encoder...")
    encoder = VoiceEncoder()
    print("Models ready.\n")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    grand_tagged = grand_skipped = grand_errors = 0

    # Handle single-MP3 mode
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
        status = process_episode(pipeline, encoder, tv_embedding, mp3_path, json_path, args.retag)
        print(f"\nResult: {status}")
        return 0

    # Batch mode: process all episodes in each requested year
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
                pipeline, encoder, tv_embedding, mp3_path, json_path, args.retag
            )
            if status == "tagged":
                grand_tagged += 1
            elif status == "skipped":
                grand_skipped += 1
            else:
                grand_errors += 1

    print(f"\n{'═' * 52}")
    print(f"Done: {grand_tagged} tagged, {grand_skipped} skipped, {grand_errors} errors")
    if grand_errors:
        print(f"Check {LOG_FILE} for details.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## Phase D — Database Schema Update

This adds the `source` column to Supabase so the data gets stored properly.

- [X] Step D1 — Create the migration SQL file

Create `web/supabase/add_source_column.sql`:

```sql
-- Add "source" column to transcript_segments
-- Values: 'TV' (Tommy Vance), 'other' (guest/soundbite), NULL (music / not yet tagged)
ALTER TABLE transcript_segments
  ADD COLUMN IF NOT EXISTS source TEXT;

-- Optional index to speed up queries that filter by source
CREATE INDEX IF NOT EXISTS idx_transcript_segments_source
  ON transcript_segments (source)
  WHERE source IS NOT NULL;
```

Run this in the Supabase SQL Editor (Dashboard → SQL Editor → paste and run).

- [X] Step D2 — Update the upload script

Open `scripts/upload_episodes.py`. Find where transcript segments are assembled into a dict for upserting. Add `"source": seg.get("source")` to that dict.

The exact location will look something like:
```python
{
    "episode_date": date,
    "start_time": seg["start"],
    "end_time": seg["end"],
    "text": seg["text"],
    # ADD THIS LINE:
    "source": seg.get("source"),   # "TV", "other", or None
}
```

- [X] Step D3 — Update the vector search (optional, recommended)

Open `web/lib/db/retrieval.ts`. In the function that calls the Supabase RPC for similarity search, add a filter so that only Tommy Vance's speech is used in retrieval by default. The exact change depends on the current code — look for the `.rpc("match_segments", ...)` call and add a `.filter("source", "eq", "TV")` chained on the query, or pass it as a parameter to the SQL function in `match_segments.sql`.

---

## Phase E — Running and Verifying

- [ ] Step E1 — Test on one episode first

```
python scripts/diarise_transcripts.py "FRSAudio/128kbps/1981/FRS 1981-04-10_128kps.mp3"
```

This takes roughly 25 minutes on CPU for a 2-hour episode. On first run, pyannote will download the model (~1GB) which adds a few minutes.

- [ ] Step E2 — Verify the output manually

Open `data/episodes/1981/FRS 1981-04-10.json`. Look at the closing exchange around 7151s–7174s. You should see:

```json
{ "start": 7151.17, "end": 7153.93, "text": "Well, Wilson, you kept it all together tonight", "source": "TV" },
{ "start": 7153.93, "end": 7155.97, "text": "So you say something nice, then", "source": "TV" },
{ "start": 7155.97, "end": 7157.79, "text": "Well, I'm off to Nottingham for the weekend", "source": "other" },
...
{ "start": 7163.83, "end": 7165.47, "text": "I'd be in every single one of them", "source": "other" },
{ "start": 7167.65, "end": 7169.13, "text": "Wine bar tonight, what do you say?", "source": "TV" },
...
{ "start": 7171.05, "end": 7173.91, "text": "This is Tommy Vance in London. God bless. Good night.", "source": "TV" }
```

Also confirm that `[Music]` segments do NOT have a `source` field added.

- [ ] Step E3 — Check the stats log

Check `logs/diarisation_errors.log` for any episodes where pyannote couldn't identify Tommy with confidence. Those will need either:
- A lower `--threshold` value (try 0.55)
- More reference clips added to `build_tv_embedding.py`

- [ ] Step E4 — Run across all episodes for a year

Once the single-episode test passes:

```
python scripts/diarise_transcripts.py --year 1981
```

- [ ] Step E5 — Quick precision check

Manually look at 30 random speech segments from 3 different episodes. Count how many `"TV"` / `"other"` labels agree with your own listening. Target: ≥ 85 % agreement.

---

## Relevant Files

- `scripts/build_tv_embedding.py` — new (Phase B)
- `scripts/diarise_transcripts.py` — new (Phase C)
- `web/supabase/add_source_column.sql` — new (Phase D)
- `scripts/upload_episodes.py` — add `source` field to upsert payload
- `scripts/validate_env.py` — add `HUGGINGFACE_TOKEN` check
- `data/tommy_vance_embedding.npy` — generated artefact (git-ignore this)
- `data/episodes/*/FRS YYYY-MM-DD.json` — modified in-place

Add to `.gitignore`:
```
data/tommy_vance_embedding.npy
data/references/
```

---

## Common Problems and Fixes

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `FileNotFoundError: pyannote/speaker-diarization-3.1` | HuggingFace token missing or licence not accepted | Re-check Step A2 |
| All segments tagged `"other"` | Tommy's similarity score below threshold | Try `--threshold 0.55`; add more reference clips |
| Build embedding crashes with `ModuleNotFoundError: soundfile` | Missing dependency | `pip install soundfile` |
| Embedding similarities all < 0.70 | Wrong MP3 or wrong timestamps in REFERENCE_SEGMENTS | Verify the timestamps by checking the JSON transcript |
| Very slow (> 2 hrs per episode) | Running fully on CPU | Expected — pyannote on CPU is slow; consider GPU or overnight batch |

---

## Scope

- **Included**: all years where both MP3s and cleaned transcripts exist
- **Not included**: improving pyannote accuracy with custom fine-tuning; sub-classifying "other" (guest / advert / lyric bleed)
- **Not changed**: `transcribe_1980.py` and `clean_transcripts.py` are untouched
