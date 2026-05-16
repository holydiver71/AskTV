# AskTV — The Friday Rock Show Archive

A high-fidelity, searchable digital index of Tommy Vance's *Friday Rock Show*. The project focuses on **Information Retrieval (IR)** — turning decades of audio into a "Librarian" AI that can provide specific citations, tracklists, and historical context.

> *"And now, let's get into the rock..."* — Tommy Vance

---

## What Is This?

The Friday Rock Show aired on BBC Radio 1 from 1978 to 1993, hosted by Tommy Vance. It was a landmark programme for heavy metal and hard rock in the UK, featuring exclusive sessions from bands like AC/DC, Iron Maiden, Def Leppard, Motörhead, and hundreds more.

**AskTV** aims to build a conversational AI that can answer questions like:
- *"What AC/DC session did Tommy Vance play in 1980?"*
- *"When did Iron Maiden first appear on the show?"*
- *"What track was playing at 45 minutes into the 25 January 1980 broadcast?"*

Every answer will cite a date and timestamp: `[1980-01-25 @ 00:45:10]`.

---

## Project Status

| Phase | Step | Description | Status |
|-------|------|-------------|--------|
| 1 | A | Audio ingestion — 49 x 1980 broadcasts at 128kbps mono MP3 | ✅ Done |
| 1 | B | Metadata scraping from Fandom Wiki (sessions + tracklists) | ✅ Done |
| 1 | C | Whisper transcription — timestamped spoken word | 🔜 Next |
| 1 | D | Shazam fingerprinting — verified track timestamps | 🔜 Next |
| 2 | A | Supabase schema migration (episodes, tracks, transcript_segments) | ⏳ Planned |
| 2 | B | Vectorisation + upload (OpenAI embeddings + pgvector) | ⏳ Planned |
| 3 | A | Next.js registry view — searchable logbook | ⏳ Planned |
| 3 | B | RAG chatbot with Tommy Vance persona | ⏳ Planned |

---

## Repository Structure

```
AskTV/                          # This repo — planning + future Next.js app
├── README.md
├── AGENTS.md                   # AI agent instructions
└── AskTV.plan.md               # Full project spec and roadmap
```

The broader project lives alongside this repo:

```
The Friday Rock Show Registry/
├── AskTV/                      # ← This repo
├── FRSAudio/128kbps/1980/      # 49 MP3s: FRS YYYY-MM-DD_128kps.mp3
├── FRSEpisodeDetailExtractor/  # Python scraper (Fandom Wiki → JSON)
│   └── output/1980/            # 49 JSON files: FRS YYYY-MM-DD.json
└── venv/                       # Shared Python environment
```

---

## Data Format

Each episode is stored as a JSON file:

```json
{
  "title": "FRS 1980-01-04",
  "url": "https://fridayrockshow.fandom.com/wiki/04_January_1980",
  "show": { "date": "1980-01-04", "comments": [] },
  "sessions": [
    { "artist": "AC/DC", "details": "recorded 1976-06-03 for John Peel" }
  ],
  "track_listing": [
    { "artist": "AC/DC", "track": "Can I Sit Next To You?", "details": "Peel session 1976-06-03" }
  ]
}
```

Enrichment steps will add:
- `transcript` — timestamped Whisper segments
- `verified_timestamp` — Shazam-confirmed track start times

---

## Scripts

### `scripts/download_episodes.py` — Download episodes from Mixcloud

Automates downloading Friday Rock Show MP3s from Mixcloud. It scrapes the [episode checklist](https://www.dawtrina.com/music/frs/checklist.html) to find the Mixcloud URL for each broadcast, then invokes `yt-dlp` to extract and save the audio as `FRS YYYY-MM-DD.mp3`.

Files are saved to `FRSAudio/Source/<year>/`.  Already-downloaded files are detected by filename and skipped automatically.

**Requirements:** `yt-dlp` on PATH (`sudo apt install yt-dlp`), plus `requests`, `beautifulsoup4`, and `lxml` in the virtual environment.

```bash
# Download all 1980 episodes
python scripts/download_episodes.py 1980

# Download only March 1981
python scripts/download_episodes.py 1981 --month 03

# Preview what would be downloaded without saving anything
python scripts/download_episodes.py 1980 --dry-run

# Pass saved browser cookies if Mixcloud requires login
python scripts/download_episodes.py 1980 --cookies-browser chrome
```

Verbose diagnostic output is printed throughout (`[FETCH]`, `[PARSE]`, `[DOWNLOAD N/TOTAL]`, `[SKIP]`, `[OK]`, `[FAIL]`, `[DONE]`), so you can see exactly what is happening at every stage.

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Transcription | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`large-v3`, `int8`) |
| Audio fingerprinting | [ShazamIO](https://github.com/dotX12/ShazamIO) |
| Database | [Supabase](https://supabase.com) + `pgvector` |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dims) |
| Frontend | Next.js + Tailwind CSS + Shadcn/UI |
| Scraper | Python 3.13, `curl-cffi`, `beautifulsoup4` |

---

## External Resources

- [Friday Rock Show Fandom Wiki](https://fridayrockshow.fandom.com/wiki) — episode metadata source
- [Episode Checklist](https://www.dawtrina.com/music/frs/checklist.html) — broadcast history
- [FRSEpisodeDetailExtractor](../FRSEpisodeDetailExtractor/README.md) — scraper documentation

---

## Scripts

Purpose and recommended running order for the repository scripts (basic examples below). Run these from the workspace root after activating the project Python environment (`source .venv/bin/activate` or your preferred virtualenv).

0. Convert to 128kbps (scripts/convert.py)
- Purpose: Convert source audio into 128kbps MP3 files used by the rest of the pipeline.
- When to run: Run this before transcription if your source audio is not already encoded as 128kbps MP3s. The repository expects files in `FRSAudio/128kbps/` for phase-1 ingestion.
- Requirements: `ffmpeg` must be installed and available on your PATH.
- Example: `python scripts/convert.py --input ../FRSAudio/Source --output ../FRSAudio/128kbps --recursive`
 - Default behavior: the script will skip existing output files by default to avoid accidental overwrites. To force overwrite, pass `--overwrite` (or `-f`).
 - Output filenames: the converter appends a bitrate label to the source basename. For example, `FRS 1980-01-04.mp3` becomes `FRS 1980-01-04_128kps.mp3` when using the default `--bitrate 128k`.
 - Preserves relative directories: the converter keeps the same subdirectory layout under the output directory (for example `1980/FRS 1980-01-04_128kps.mp3`).

Example mapping:
```
Source: ../FRSAudio/Source/1980/FRS 1980-01-04.mp3
Output: ../FRSAudio/128kbps/1980/FRS 1980-01-04_128kps.mp3
```

1. Transcription
- Purpose: Run Whisper to produce raw, timestamped transcript JSON for each episode audio file.
- Example: `python scripts/transcribe_1980.py --year 1980`

2. Fingerprinting (Shazam)
- Purpose: Probe audio (short samples) to detect tracks and write `verified_timestamp` entries into episode JSON files.
- Example: `python scripts/shazam_1980.py --year 1980`

3. Cleaning / Post-processing
- Purpose: Run the multi-phase cleaner that strips hallucinations, trims extreme-duration segments, and inserts `[Music]` placeholders where appropriate. This produces the final cleaned `transcript` arrays in the episode JSON files.
- Example: `python scripts/clean_transcripts.py --year 1980`

4. Address redaction
- Purpose: Redact listener postal addresses (house number + street name) from the cleaned transcript segments, replacing them with `[redacted address]` while preserving the area/region. The BBC Radio 1 broadcaster address is never redacted.
- When to run: After `clean_transcripts.py`. Works on the `transcript` arrays already present in the episode JSON files.
- Example: `python scripts/redact_addresses.py`

5. Lyrics detection (optional)
- Purpose: Cross-reference `track_listing` entries against Genius lyrics and flag any lyric snippets that remain in the cleaned transcript segments. Useful for identifying music content that Whisper transcribed rather than labelling as `[Music]`.
- When to run: After `clean_transcripts.py` and `redact_addresses.py`. Requires a Genius API token.
- Example: `GENIUS_API_TOKEN="YOUR_TOKEN" python scripts/check_lyrics_in_transcripts.py --episodes-dir data/episodes --output logs/lyrics_flags.json`

Notes:
- Run the steps in the above order for best results: conversion (if needed) → transcription → fingerprinting → cleaning → address redaction → lyrics detection.
- Use `--year` (or the script-specific flags) to scope runs to a single year or set of files where supported.
- Logs are written to the `logs/` directory (this is ignored by Git).

### `scripts/redact_addresses.py` — Redact listener postal addresses

Purpose: scan every `transcript` segment in the episode JSON files and replace listener house numbers and street names with `[redacted address]`. Area, town, and region information is preserved. The BBC Radio 1 broadcaster address (`BBC Radio 1, London, W1A4WW`) is never redacted.

Handles:
- Standard numeric addresses — `224 Chester Road` → `[redacted address]`
- Written house numbers — `Five Somerdale Gardens` → `[redacted address]`
- `No.` / `number` prefixed addresses — `No. 5 Green Lodge Terrace`, `number 40 Queensway`
- Flat/apartment prefixes — `Flat One, 7 Travis Place`
- Multi-segment splits where the street name bleeds into the next transcript tag

**When to run:** After `scripts/clean_transcripts.py` and before any database upload or public-facing use.

Basic usage (run from the workspace root):

```bash
# Redact all 1980 episodes in-place
python scripts/redact_addresses.py

# Preview changes without writing any files
python scripts/redact_addresses.py --dry-run
```

The script writes a log to `logs/redact_addresses.log` showing the number of redactions per episode and a grand total.

---

### `scripts/check_lyrics_in_transcripts.py` — Detect leftover song lyrics in transcripts

Purpose: look up song lyrics (Genius) for each `track_listing` entry and check whether lyric snippets remain in the cleaned `transcript` segments. Flags are written to a JSON report (default `logs/lyrics_flags.json`) and, when requested, a `lyrics_flag` and `lyrics_match_snippet` are added to the matching `track_listing` entry in the episode JSON.

Requirements:
- `requests`, `beautifulsoup4` (install in the project virtualenv)
- A Genius API token exported as `GENIUS_API_TOKEN` in your shell environment

Important notes:
- Run this after `scripts/clean_transcripts.py` to flag residual lyric text left in the cleaned transcripts.
- The script uses the Genius web pages to extract lyrics; be mindful of rate limits and polite scraping. Use the `--write` flag to annotate episode JSON files in-place. Increase timing delays in the script if you hit rate limits.

Basic usage examples (run from the workspace root):

Single episode (report only):
```bash
GENIUS_API_TOKEN="YOUR_TOKEN_HERE" python3 scripts/check_lyrics_in_transcripts.py --episode 'data/episodes/1980/FRS 1980-01-04.json' --output logs/lyrics_flags.json
```

All episodes (report only):
```bash
GENIUS_API_TOKEN="YOUR_TOKEN_HERE" python3 scripts/check_lyrics_in_transcripts.py --episodes-dir data/episodes --output logs/lyrics_flags.json
```

All episodes and write flags back into the episode JSON files:
```bash
GENIUS_API_TOKEN="YOUR_TOKEN_HERE" python3 scripts/check_lyrics_in_transcripts.py --episodes-dir data/episodes --write --output logs/lyrics_flags.json
```

The output JSON contains entries like:

```
[
  {
    "episode": "data/episodes/1980/FRS 1980-01-04.json",
    "track_index": 2,
    "artist": "AC/DC",
    "title": "Can I Sit Next To You?",
    "genius_url": "https://genius.com/...",
    "matched_snippet": "can i sit next to",
    "match_type": "exact",
    "transcript_start": 1327.9
  }
]
```

This `transcript_start` value is the `start` attribute of the transcript element where the match was found, so you can jump directly to the segment in the episode JSON for manual review.

---

## Licence

Research and archival project. No audio is hosted or distributed.
