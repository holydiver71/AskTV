# Plan: Transcript Cleanup — Lyrical Muzzling & Silence Stripping

**TL;DR**: The raw Whisper output is polluted with ellipsis-only silence placeholders and song lyrics. A new `clean_transcripts.py` script handles both in two phases: ellipsis stripping runs immediately (no dependencies), lyrical muzzling runs after the Shazam step produces `verified_timestamp` data.

---

## Phase 1 — Immediate: Ellipsis Stripper

New script: `scripts/clean_transcripts.py`

- [x] 1. Iterate all JSONs in `data/episodes/1980/`
- [x] 2. Filter `transcript` array — drop any segment where `text.strip()` matches `^\.*$` (pure dots, empty, or `"..."`)
- [x] 3. Atomic write-back using `.tmp` → `os.replace()` pattern (same as `transcribe_1980.py`)
- [x] 4. Log counts per file: `[YYYY-MM-DD] Removed N ellipsis segments`
- [x] 5. Script must be idempotent — safe to re-run after Phase 2 is added

---

## Phase 2 — After Shazam: Lyrical Muzzler

Extend the same `clean_transcripts.py` script. Gated: only activates when `verified_timestamp` fields are present on `track_listing` entries.

- [x] 6. For each `track_listing` entry with a `verified_timestamp`:
  - Compute `song_start = verified_timestamp` (seconds float)
  - Compute `song_end` = next track's `verified_timestamp - 5s` (overlap buffer), or use audio duration for the last track
- [ ] 7. Remove all `transcript` segments fully enclosed in `[song_start, song_end]`
- [ ] 8. Insert a single placeholder segment: `{"start": song_start, "end": song_end, "text": "[Music: Artist - Track Title]", "type": "music"}`
- [ ] 9. Segments outside verified track windows are untouched — Tommy's speech, station IDs, FNC segments preserved
- [ ] 10. Log: `[YYYY-MM-DD] Muzzled N lyric segments for 'Artist - Track'`

---

## Relevant Files
- `scripts/clean_transcripts.py` — new script (both phases, Phase 2 self-gates on presence of `verified_timestamp`)
- `scripts/transcribe_1980.py` — reference for atomic write pattern and path constants to reuse
- `data/episodes/1980/*.json` — modified in-place

---

## Verification
1. After Phase 1: `python -c "import json; d=json.load(open('data/episodes/1980/FRS 1980-01-04.json')); print(sum(1 for s in d['transcript'] if s['text'].strip()=='...'))"` → must print `0`
2. Segment count for `FRS 1980-01-04.json` before vs. after — expect significant reduction (the file currently has hundreds of `"We'll be right back."` / `"..."` entries spanning 30-second increments)
3. After Phase 2: Inspect `transcript` around a known `verified_timestamp` — confirm single `[Music: ...]` placeholder replaces the block of lyric segments
4. Confirm Tommy Vance speech segments (e.g. the ACDC intro at ~3572s, the FNC segment at ~3575s) survive the muzzle pass untouched
5. `git diff data/episodes/1980/FRS\ 1980-01-04.json` — confirms only unwanted rows removed, no speech lost

---

## Decisions
- Post-processing chosen over VAD tuning or Whisper prompting — triangulation is more reliable and auditable
- `"We'll be right back."` repeated segments (ads/music bed) are **not** stripped in Phase 1 — they carry a valid timestamp and may help locate ad breaks. Phase 2 will muzzle them only if they fall within a verified track window
- Music placeholder `type: "music"` field added for clean Supabase filtering downstream
- Phase 2 is self-gating — running `clean_transcripts.py` now (before Shazam) is safe and only does Phase 1
