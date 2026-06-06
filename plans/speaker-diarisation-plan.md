# Plan: Speaker Diarisation — Tommy Vance Voice Identification

**Goal**: Enrich transcript segments with a `source` field indicating who is speaking.  
Possible values:
- `"TV"` — Tommy Vance presenting
- `"other"` — another voice (guest, co-presenter, soundbite, misidentified lyric fragment)

Segments that already carry `"type": "music"` (the `[Music: …]` placeholders written by `clean_transcripts.py`) are left untouched — they are not speech.

---

## Approach Overview

Speaker diarisation is a **post-processing step** that runs *after* Whisper transcription and *after* `clean_transcripts.py` has applied the lyric muzzle. It reads the existing MP3 and JSON, assigns speaker identities to each speech segment, and writes back `source` tags.

### Why a separate script?
The existing architecture separates concerns cleanly (transcribe → clean → shazam → vectorise). Speaker diarisation should not block transcription and can be safely re-run. A standalone `scripts/diarise_transcripts.py` follows the same pattern as `clean_transcripts.py`.

### Technology stack

| Component | Library | Purpose |
|-----------|---------|---------|
| Speaker diarisation | `pyannote.audio` ≥ 3.x | Segment audio into labelled speaker turns |
| Speaker verification | `resemblyzer` | Build a Tommy Vance voice embedding; identify which diarised cluster is him |
| Audio extraction | `pydub` / `ffmpeg` | Slice reference clips from known Tommy Vance segments |

**Why `pyannote.audio`?**  
It is the de-facto open-source speaker diarisation stack, runs on CPU (slow) or GPU (fast), and produces speaker-labelled time intervals that can be cross-referenced directly against the Whisper `start`/`end` timestamps.

**Why `resemblyzer`?**  
It uses a pre-trained GE2E speaker encoder to produce a 256-dim d-vector for any speech clip. No HuggingFace token required. Tommy Vance's voice is distinctive (deep, authoritative BBC register) — a single reference embedding is sufficient for binary TV / other classification.

> **Alternative if GPU memory is tight**: `speechbrain` ECAPA-TDNN model can replace `resemblyzer` with a smaller memory footprint and marginally higher accuracy.

---

## Phase 1 — Reference Voice Profile

### 1.1 Identify reference segments
Use existing transcripts to extract timestamps of *known* Tommy Vance speech. Ideal candidates are clean studio monologue segments (no background music, not too short):

- Intro/outro paragraphs (first 120 s of most episodes)
- Track introductions ("And now here's…", "That was…")
- The sign-off ("This is Tommy Vance in London. God bless. Good night.")

A helper script or one-liner can extract 5–10 reference clips:
```python
# Pseudo-code — enumerate intro segments from the 1980 corpus
for json_file in data/episodes/1980/*.json:
    take first non-music transcript segment > 4 s
    write clip to references/tommy_vance_ref_<date>.wav using pydub
```

### 1.2 Build the mean d-vector
```python
from resemblyzer import VoiceEncoder, preprocess_wav
encoder = VoiceEncoder()
embeddings = [encoder.embed_utterance(preprocess_wav(clip)) for clip in reference_clips]
tv_embedding = np.mean(embeddings, axis=0)  # shape (256,)
np.save("data/tommy_vance_embedding.npy", tv_embedding)
```

- [ ] 1. Extract ≥ 5 reference WAV clips from known TV intro segments (use `pydub`, auto-select from transcript)
- [ ] 2. Compute mean d-vector and save to `data/tommy_vance_embedding.npy`
- [ ] 3. Spot-check: cosine similarity between any two TV reference clips should be ≥ 0.80

---

## Phase 2 — Per-Episode Diarisation

For each episode MP3 (or all episodes in a year):

### 2.1 Run pyannote.audio speaker diarisation
```python
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=HUGGINGFACE_TOKEN,  # read from .env / env var
)
diarisation = pipeline(mp3_path)
# Returns Annotation object: {speaker_id: [(start, end), ...]}
```

> **HuggingFace token**: pyannote pretrained models require accepting the model card on HuggingFace and setting `HUGGINGFACE_TOKEN` in `.env`. Add `HUGGINGFACE_TOKEN=` to `.env.example` and document in README.

### 2.2 Extract per-speaker audio clips and embed them
For each speaker cluster returned by pyannote, take up to 30 s of audio and compute a d-vector:
```python
speaker_embeddings = {}
for speaker, turns in diarisation.itertracks():
    clip = extract_audio_clip(mp3, turns[:30s])
    speaker_embeddings[speaker] = encoder.embed_utterance(clip)
```

### 2.3 Classify: which cluster is Tommy Vance?
```python
similarities = {spk: cosine_sim(emb, tv_embedding) for spk, emb in speaker_embeddings.items()}
tv_speaker_id = max(similarities, key=similarities.get)
# Sanity threshold — if max similarity < 0.65 flag episode for manual review
```

### 2.4 Map diarisation turns onto transcript segments
For each Whisper transcript segment (non-music):
1. Find which speaker turn has the greatest overlap with `[start, end]`.
2. If overlap ≥ 50 % of segment duration: assign that speaker.
3. If no turn overlaps by ≥ 50 %: mark `"source": "other"` (ambiguous).

```python
def dominant_speaker(seg_start, seg_end, turns_by_speaker):
    best_speaker, best_overlap = None, 0.0
    for speaker, turns in turns_by_speaker.items():
        overlap = sum_overlap(seg_start, seg_end, turns)
        if overlap > best_overlap:
            best_speaker, best_overlap = speaker, overlap
    return best_speaker if best_overlap / (seg_end - seg_start) >= 0.5 else None
```

### 2.5 Write `source` field back to JSON
```python
for seg in transcript:
    if seg.get("type") == "music":
        continue  # leave music placeholders alone
    speaker = dominant_speaker(seg["start"], seg["end"], diarisation_turns)
    seg["source"] = "TV" if speaker == tv_speaker_id else "other"
atomic_write(json_path, episode_data)
```

- [ ] 4. Install dependencies: `pip install pyannote.audio resemblyzer pydub`
- [ ] 5. Add `HUGGINGFACE_TOKEN` to `.env.example` and `scripts/validate_env.py`
- [ ] 6. Write `scripts/diarise_transcripts.py` with:
  - `--year` / `--mp3` arguments (same interface as `transcribe_1980.py`)
  - `--retag` flag to overwrite existing `source` fields
  - `--threshold` float (default 0.65) for TV cosine similarity cutoff
  - `--ref-embedding` path (default `data/tommy_vance_embedding.npy`)
  - SIGINT-safe loop with atomic write-back
  - Structured log file `logs/diarisation_errors.log`
- [ ] 7. Run against a single test episode; inspect output manually
- [ ] 8. Run across all 1980 episodes; log episodes where TV similarity < threshold

---

## Phase 3 — Integration & Schema

### 3.1 Upstream schema changes
The `source` field is additive — existing segments without it default to `null` (no assumption). No migrations needed for existing data.

For Supabase `transcript_segments` table, add the column:
```sql
ALTER TABLE transcript_segments ADD COLUMN IF NOT EXISTS source TEXT;
-- Values: 'TV', 'other', NULL (unknown / music)
```

Add to `scripts/upload_episodes.py`: map `seg.get("source")` → `source` column.

- [ ] 9. Write and apply `supabase/add_source_column.sql` migration
- [ ] 10. Update `scripts/upload_episodes.py` to include `source` field in upsert payload
- [ ] 11. Update `scripts/vectorise_transcripts.py` — optionally skip `source == "other"` segments or tag them differently in the embedding store (to avoid lyrics polluting vector search)

### 3.2 RAG quality improvement
With `source` tags, the retrieval query in `lib/db/retrieval.ts` can be filtered:
```sql
WHERE source = 'TV' OR source IS NULL
```
This prevents retrieved context from containing lyric fragments or soundbites that Whisper captured but weren't muzzled by Shazam (because no `verified_timestamp` existed for that track).

- [ ] 12. Update `lib/db/retrieval.ts` vector search to filter `source = 'TV'` by default, with an optional override flag for full-corpus search

---

## Phase 4 — Validation

- [ ] 13. **Known-good check**: episode `1981-04-10` — the closing exchange between Tommy and Tony Wilson ("Wine bar tonight…", "This is Tommy Vance in London. God bless. Good night.") should produce:
  - Tommy lines: `"source": "TV"`
  - Wilson's lines ("I'd be in every single one of them", "Pub crawl freak he is", "Wine bar tonight, what do you say?"): `"source": "other"`
- [ ] 14. **Lyric bleed check**: confirm segments with `"type": "music"` have no `source` field added
- [ ] 15. **Precision/recall spot-check**: manually label 30 random segments from 3 episodes; compare against script output; target precision ≥ 85 %

---

## Estimated Compute

| Step | Time (CPU) | Time (GPU, RTX 3080) |
|------|-----------|----------------------|
| Reference embedding build | < 2 min | < 30 s |
| pyannote diarisation per 2-hr episode | ~25 min | ~3 min |
| resemblyzer embedding per episode | ~2 min | ~20 s |
| Full 1980 corpus (49 eps) | ~20 hrs | ~2.5 hrs |

> Run the GPU path if available. pyannote auto-detects CUDA via `torch`.

---

## Dependencies (add to `requirements.txt`)

```
pyannote.audio>=3.1.0
resemblyzer>=0.1.1
pydub>=0.25.1
```

> `pydub` requires `ffmpeg` on PATH (already a project dependency).

---

## Relevant Files
- `scripts/diarise_transcripts.py` — new script (this plan)
- `scripts/transcribe_1980.py` — reference for arg parser, atomic write, SIGINT pattern
- `scripts/clean_transcripts.py` — reference for transcript iteration pattern
- `data/tommy_vance_embedding.npy` — persisted TV voice profile (new)
- `supabase/add_source_column.sql` — DB migration (new)
- `data/episodes/*/FRS YYYY-MM-DD.json` — modified in-place

---

## Decisions

- **Post-processing not in-transcription**: speaker diarisation and ASR are best run separately; combining them in one pass would require Whisper-X (which forces whisper-base/small alignment models) and loses the tuned `large-v3` quality we already have.
- **resemblyzer over pyannote speaker embedding**: pyannote's own embedding model also works, but resemblyzer is simpler to use for binary classification without requiring a second HuggingFace token.
- **Threshold 0.65**: cosine similarity in d-vector space; empirically robust for a distinctive voice like Tommy's deep baritone. Adjust via `--threshold` if needed.
- **`other` not sub-classified**: distinguishing "co-presenter" vs "soundbite" vs "lyric bleed" would require additional models; `other` is sufficient for the RAG filtering goal.
- **`source` field omitted from `[Music]` segments**: these are already typed as `"type": "music"` — adding a second classification field would be redundant and confusing.
