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

## Licence

Research and archival project. No audio is hosted or distributed.
