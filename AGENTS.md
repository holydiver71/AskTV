# Friday Rock Show Archive — Agent Instructions

## Project Overview
A high-fidelity, searchable digital index of Tommy Vance's *Friday Rock Show*. The goal is **Information Retrieval (IR)**: building a "Librarian" AI that answers questions with citations and timestamps. No music hosting.

See [AskTV.plan.md](AskTV.plan.md) for the full project spec, phase breakdown, and roadmap.

## Repository Layout

```
The Friday Rock Show Registry/
├── AskTV/                          # ← This workspace (planning + future Next.js app)
├── FRSAudio/
│   ├── 128kbps/1980/               # MP3s: FRS YYYY-MM-DD_128kps.mp3
│   └── Source/
├── FRSEpisodeDetailExtractor/      # Python scraper (see its README)
│   ├── extractor.py
│   ├── requirements.txt
│   └── output/1980/                # JSON: FRS YYYY-MM-DD.json
└── venv/                           # Shared Python venv
```

## File Naming & Matching
- **Audio**: `FRS YYYY-MM-DD_128kps.mp3`
- **JSON metadata**: `FRS YYYY-MM-DD.json`
- **Always match files by the `YYYY-MM-DD` date string** extracted from the filename.

## JSON Episode Schema
```json
{
  "title": "FRS YYYY-MM-DD",
  "url": "https://fridayrockshow.fandom.com/wiki/...",
  "show": { "date": "YYYY-MM-DD", "comments": [] },
  "sessions": [{ "artist": "...", "details": "..." }],
  "track_listing": [{ "artist": "...", "track": "...", "details": "..." }]
}
```
Enrichment steps append to this structure:
- **Step C** adds: `"transcript": [{ "start": float, "end": float, "text": str }]`
- **Step D** adds: `"verified_timestamp"` to matched `track_listing` entries

## Python Environment
- **Runtime**: Python 3.13
- **Venv**: `../venv/` (relative to this workspace), or `FRSEpisodeDetailExtractor/.venv/` for the scraper
- **Key packages**: `faster-whisper`, `shazamio`, `supabase`, `openai`, `curl-cffi`, `beautifulsoup4`
- **Whisper config**: model `large-v3`, quantization `int8` (CPU-optimised)

## Processing Rules
1. **Whisper transcription**: Iterate `FRSAudio/128kbps/1980/`, match each MP3 to its JSON by date, append `transcript` array.
2. **Shazam fingerprinting**: 15-second probes every 180 seconds; cross-reference against `track_listing`; write `verified_timestamp` on match.
3. **Error handling**: Log failed transcriptions and Shazam mismatches; do not abort the full run on a single failure.

## Plan Tracking
All phase plans live in `plans/`. Each plan step has a checkbox (`- [ ]`). **When executing any plan step, mark its checkbox as complete (`- [x]`) immediately after the step succeeds.** If a step fails or is skipped, leave it unchecked and add a brief inline note.

## Key External Resources
- **Fandom Wiki** (episode metadata source): https://fridayrockshow.fandom.com/wiki
- **Episode checklist**: https://www.dawtrina.com/music/frs/checklist.html
- **Scraper README**: [FRSEpisodeDetailExtractor/README.md](../FRSEpisodeDetailExtractor/README.md)

## Future Stack (Phase 2–3)
- **Database**: Supabase with `pgvector` (1536-dim OpenAI embeddings)
- **Tables**: `episodes`, `tracks`, `sessions`, `transcript_segments`
- **Frontend**: Next.js + Tailwind CSS + Shadcn/UI
- **Chatbot persona**: Tommy Vance style; every answer must cite `[YYYY-MM-DD @ HH:MM:SS]`

All python code generated or changed must be linted. Do not report a task as being done until not linting issues exist in the code. 
