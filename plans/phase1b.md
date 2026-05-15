# Plan: Phase 1B — Shazam Music Fingerprinting

**TL;DR**: Create `scripts/shazam_1980.py` — an async script that probes each 1980 MP3 every 180s with 15-second audio slices, identifies tracks via ShazamIO, fuzzy-matches against `track_listing` entries, and writes `verified_timestamp` (seconds float) to matched entries. Once written, `clean_transcripts.py` Phase 2 (lyrical muzzling) activates automatically.

---

## Phase 0 — Environment Setup

- [x] 1. Install into `.venv/`:
  ```
  source .venv/bin/activate
  pip install shazamio rapidfuzz
  ```
  - `shazamio` — async Shazam API client
  - `rapidfuzz` — fuzzy artist/track matching
  - Note: `pydub` is NOT needed — audio slicing is done via direct ffmpeg subprocess

---

## Phase 1 — Write `scripts/shazam_1980.py`

- [x] 2. **Constants block**:
  - `AUDIO_DIR` → `/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/128kbps/1980/`
  - `JSON_DIR` → `data/episodes/1980/`
  - `LOG_FILE` → `logs/shazam.log`
  - `PROBE_INTERVAL = 180` (seconds between probe start points)
  - `PROBE_DURATION = 15` (seconds per probe slice)
  - `MATCH_THRESHOLD = 80` (rapidfuzz `token_sort_ratio` minimum)
  - `PROBE_DELAY = 1.5` (seconds sleep between API calls — rate limiting)

- [x] 3. **Audio extraction helper** `extract_probe(mp3_path: Path, offset_s: int, duration_s: int) -> bytes`:
  - ffmpeg subprocess: `ffmpeg -ss {offset_s} -t {duration_s} -i {mp3_path} -f wav -ac 1 -ar 16000 pipe:1`
  - Capture `stdout` bytes — no temp files written to disk
  - Raise `RuntimeError` on non-zero ffmpeg returncode, including stderr in message

- [x] 4. **Fuzzy match helper** `find_best_match(shazam_title: str, shazam_artist: str, track_listing: list) -> int | None`:
  - Build candidate string `f"{entry['artist']} {entry['track']}"` for each entry in `track_listing`
  - Compare against `f"{shazam_artist} {shazam_title}"` using `rapidfuzz.fuzz.token_sort_ratio`
  - Skip entries already having a `verified_timestamp` key (first/earliest match wins, cannot be overwritten)
  - Return index of best match if score ≥ `MATCH_THRESHOLD`, else `None`

- [x] 5. **Async episode processor** `async def process_episode(mp3_path: Path, json_path: Path, shazam: Shazam) -> None`:
  - Load JSON; derive audio duration from `data["transcript"][-1]["end"]` (all episodes are already transcribed)
  - Compute "stampable" count: `track_listing` entries that have NO `verified_timestamp` AND whose `details` field does NOT contain "session" (case-insensitive)
  - **Idempotency gate**: if stampable count == 0, log `[YYYY-MM-DD] Skipping — fully stamped` and return
  - Iterate offsets: `for offset in range(0, int(audio_duration), PROBE_INTERVAL):`
    1. `audio_bytes = extract_probe(mp3_path, offset, PROBE_DURATION)`
    2. `result = await shazam.recognize_song(audio_bytes)` — wrap in `try/except` to log and continue on network/API error
    3. Extract `title = result["track"]["title"]` and `artist = result["track"]["subtitle"]` — skip probe if `"track"` key absent (no match)
    4. `idx = find_best_match(title, artist, track_listing)`
    5. If matched: set `track_listing[idx]["verified_timestamp"] = float(offset)`, log `[YYYY-MM-DD] ✓ Matched: {artist} – {title} @ {offset}s`
    6. `await asyncio.sleep(PROBE_DELAY)`
  - **Atomic write-back once** after all probes complete (not per-probe): write to `.tmp` then `os.replace()`
  - Log summary: `[YYYY-MM-DD] Done — {n_matched} new timestamp(s) written`

- [x] 6. **Graceful Ctrl+C**: catch `KeyboardInterrupt` in the main loop — finish the current episode's write-back, then `break`. Print `"\nInterrupt received — stopping after current episode."` Never exits mid-write.

- [x] 7. **Main async entry point** `async def main()`:
  - Glob `AUDIO_DIR` for `*.mp3`; extract date with `re.search(r'\d{4}-\d{2}-\d{2}', filename)`
  - Pair with `JSON_DIR / f"FRS {date}.json"` — log warning and skip if JSON not found
  - Instantiate `Shazam()` once before the loop
  - Iterate episodes in date order; print `[N/49] Processing YYYY-MM-DD…` per episode
  - `asyncio.run(main())` at module entry point

---

## Phase 2 — Run & Activate Muzzling

- [x] 8. *(Manual)* Run the fingerprinting script:
  ```
  source .venv/bin/activate
  python scripts/shazam_1980.py
  ```
  - Resume-safe: re-running skips fully-stamped episodes
  - Expected: session tracks (Peel, FRS, Top Gear sessions) will NOT match Shazam — this is correct, not an error
  - Expected LP match rate: ~40–70% (Shazam DB coverage for 1980s rock varies)

- [x] 9. *(Manual)* Once fingerprinting is complete (or after each session), re-run transcript cleanup to activate Phase 2 lyrical muzzling:
  ```
  python scripts/clean_transcripts.py
  ```
  Phase 2 self-activates automatically on the presence of `verified_timestamp` fields — no code changes needed.

---

## Relevant Files

| File | Action |
|---|---|
| `scripts/shazam_1980.py` | **CREATE** — main deliverable |
| `data/episodes/1980/FRS YYYY-MM-DD.json` × 49 | **MODIFIED** in-place — `verified_timestamp` added to matched LP tracks |
| `scripts/clean_transcripts.py` | **NO CHANGES** — Phase 2 already stubbed, self-gates on data |
| `logs/shazam.log` | Created at runtime |

---

## Verification

- [x] 1. Spot-check first episode after run:
  ```
  python -c "import json; d=json.load(open('data/episodes/1980/FRS 1980-01-04.json')); [print(t['artist'], '-', t['track'], '->', t.get('verified_timestamp','UNMATCHED')) for t in d['track_listing']]"
  ```
- [x] 2. Count all stamped tracks across all episodes:
  ```
  python -c "import json,glob; ts=[t for f in glob.glob('data/episodes/1980/*.json') for t in json.load(open(f))['track_listing'] if 'verified_timestamp' in t]; print(len(ts), 'verified timestamps')"
  ```
- [x] 3. Review `logs/shazam.log` — session tracks should show no match (expected); LP tracks show `✓ Matched`
- [x] 4. `git diff "data/episodes/1980/FRS 1980-01-04.json"` — confirm only `verified_timestamp` fields added, no other changes
- [x] 5. Run `python scripts/clean_transcripts.py` → log must show `Phase 2 active — N verified track window(s) computed` for at least one episode

---

## Decisions & Scope Boundaries

- `verified_timestamp` = probe offset in seconds (float) where Shazam first recognised the track. Not corrected for intra-song position — that is a future enhancement.
- Session tracks (details containing "session", case-insensitive) are **excluded** from stampable targets. No error is raised when they don't match — it is expected.
- **First match wins** — `verified_timestamp` is never overwritten by a later probe.
- Atomic write-back happens **once per episode** (after all probes) for consistency and minimal I/O.
- Completing `clean_transcripts.py` steps 7–10 (segment removal + `[Music: …]` placeholder insertion) is **out of scope** for this plan.

---

## Further Considerations

1. **Runtime estimate**: 49 episodes × ~40 probes × 1.5s delay ≈ ~50 minutes wall-clock just for rate-limit sleeps, plus network round-trips. Tune `PROBE_DELAY` down if network is reliable.
2. **Unmatched LP tracks**: log these clearly at the end of each episode run so gaps are visible and can be manually patched if needed.
3. **ShazamIO API changes**: the library wraps an unofficial API — if `result["track"]` structure changes, the key-access logic in step 5 will need updating.
