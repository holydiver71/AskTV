# Phase 1 Step A — Transcription Engine

**TL;DR**: Copy the 49 existing JSON files into `AskTV/data/episodes/1980/` (version-controlled), create `AskTV/.venv/` with `faster-whisper`, then run a Python script that transcribes each MP3 and augments the local JSON files in-place.

---

## Phase 0: Repo & Environment Setup

- [X] 1. **(Manual)** Create the data folder and copy JSONs:
   ```
   mkdir -p data/episodes/1980
   cp "/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSEpisodeDetailExtractor/output/1980/"*.json data/episodes/1980/
   ```
- [X] 2. **(Manual)** Add `.venv/` and `logs/` to `.gitignore` (create it if it doesn't exist in `AskTV/`)
- [ ] 3. **(Manual)** Commit the raw JSONs as a baseline — this gives a clean git diff showing exactly what the transcription step adds to each file
- [ ] 4. **(Manual)** Create and activate venv:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install faster-whisper
   ```

---

## Phase 1: Write `scripts/transcribe_1980.py`

- [ ] 5. Create `AskTV/scripts/transcribe_1980.py`:
   - **Constants**: `AUDIO_DIR` pointing to `FRSAudio/128kbps/1980/` (MP3s stay where they are — too large for git), `JSON_DIR` pointing to `AskTV/data/episodes/1980/`, `LOG_FILE` pointing to `AskTV/logs/transcription_errors.log`
   - **Model loading**: `WhisperModel("large-v3", device="cpu", compute_type="int8")` — loaded once before the loop
   - **File discovery**: Glob `AUDIO_DIR` for `*.mp3`, extract date with `re.search(r'\d{4}-\d{2}-\d{2}', filename)`
   - **JSON matching**: Construct `JSON_DIR / f"FRS {date}.json"` — log and skip if not found
   - **Idempotency**: Skip any JSON that already has a `"transcript"` key — safe to resume after interruption
   - **Graceful shutdown**: Register a `signal.signal(SIGINT, handler)` at startup that sets a `stop_requested` flag. The handler prints `"\nInterrupt received — will stop after current file finishes."` and does **not** raise. After each file's write-back completes, check the flag and `break` out of the loop cleanly. This means Ctrl+C never corrupts an in-progress file.
   - **Transcription**: `model.transcribe(str(mp3_path), language="en", beam_size=5)` — build segments as `{"start": seg.start, "end": seg.end, "text": seg.text.strip()}`
   - **Atomic write-back**: Write to `.tmp` then `os.replace()` to avoid corrupt files if interrupted mid-write
   - **Error handling**: `try/except` per file — log timestamped failures to `logs/transcription_errors.log`, `continue` to next file
   - **Progress**: Print `[N/49] Processing YYYY-MM-DD...` per file

---

## Phase 2: Run the Script

- [ ] 6. **(Manual)** Run in a terminal session. Press Ctrl+C at any time to stop cleanly after the current file finishes:
   ```
   source .venv/bin/activate
   python scripts/transcribe_1980.py
   ```
   Re-run the same command to resume — already-transcribed files are skipped automatically.

---

## Verification

- [ ] 1. After first file completes, inspect its JSON — confirm `transcript` array is present with `start`, `end`, `text` fields
- [ ] 2. Use `git diff data/episodes/1980/FRS\ 1980-01-04.json` to see exactly what was added
- [ ] 3. After full run: `python -c "import json,glob; fs=glob.glob('data/episodes/1980/*.json'); print(sum(1 for f in fs if 'transcript' in json.load(open(f))), '/ 49')"` should print `49 / 49`
- [ ] 4. Review `logs/transcription_errors.log` for any failures

---

## Key Files

| File | Action |
|---|---|
| `AskTV/data/episodes/1980/FRS YYYY-MM-DD.json` × 49 | **Copy in + version-control**, then augmented by script |
| `AskTV/scripts/transcribe_1980.py` | **Create** — main automation script |
| `AskTV/.gitignore` | **Create/update** — exclude `.venv/`, `logs/` |
| `AskTV/logs/transcription_errors.log` | Created at runtime |

---

## Runtime Estimate

~98 hrs of audio at 0.3–0.7× real-time on CPU = **140–330 hours**. The idempotency safeguard means you can stop and resume freely at any point.
