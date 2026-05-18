# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

AskTV is a searchable digital archive of Tommy Vance's *Friday Rock Show* (1978–1993). The system is Information Retrieval (IR) first: a RAG chatbot that answers questions about episodes with citations grounded in transcripts, never speculating beyond the retrieved data. No music is hosted.

## Commands

All frontend commands run from `web/`:

```bash
cd web
npm run dev          # Dev server on port 3000
npm run build        # Production build
npm run lint         # ESLint check
npm run test:run     # Vitest single run
npm run test         # Vitest watch mode
```

Python scripts run from the workspace root with the virtual environment active:

```bash
source .venv/bin/activate  # or ../venv/bin/activate depending on location
python scripts/extractor.py                    # Scrape Fandom Wiki → JSON
python scripts/transcribe_1980.py --year 1980  # Whisper transcription
python scripts/shazam_1980.py --year 1980      # Audio fingerprinting
python scripts/clean_transcripts.py --year 1980
python scripts/vectorise_transcripts.py --year 1980
```

All Python code must pass linting before a task is marked complete.

## Repository Layout

```
askTV/
├── scripts/        # Python data processing pipeline (sequential phases)
├── data/episodes/  # JSON episode files: FRS YYYY-MM-DD.json
├── plans/          # Phase plans with checkboxes — mark steps done as they complete
└── web/            # Next.js frontend application
    ├── app/
    │   ├── chat/           # Conversational UI
    │   ├── registry/       # Searchable episode index + [date] detail pages
    │   └── api/chat/       # Chat orchestration route handler
    ├── lib/
    │   ├── ai/             # Provider abstraction + Tommy Vance system prompt
    │   ├── db/             # Supabase queries and vector retrieval RPC
    │   └── supabase/       # Client/server Supabase singletons
    └── components/         # UI components including shadcn/ui primitives
```

## Architecture

### Data Pipeline (Python, one-time processing)
Scripts run in order: extract metadata → download → convert to 128kbps → transcribe (Whisper `large-v3`, `int8`) → fingerprint (ShazamIO, 15s probes every 180s) → clean → vectorise → upload to Supabase.

Files are matched exclusively by the `YYYY-MM-DD` date string in filenames. A single script failure must log and continue, not abort the full run.

### Web Application (Next.js, App Router)
Request flow: `app/chat` UI → `app/api/chat/route.ts` → `lib/ai/*` (OpenAI generation) + `lib/db/retrieval.ts` (pgvector similarity search via Supabase RPC) → JSON response.

- **Route handlers are thin**: validate input with Zod, coordinate services, map to stable error codes (`invalid_request`, `retrieval_not_configured`, `provider_timeout`).
- **Provider abstraction**: all model-specific logic lives in `lib/ai/`; callers use typed interfaces.
- **Server/client separation**: `lib/supabase/server.ts` and secrets stay server-only; `lib/supabase/client.ts` for browser use.
- **Compatibility shims**: legacy Supabase RPC signatures are supported gracefully — preserve these fallbacks.

### Database (Supabase / PostgreSQL + pgvector)
Tables: `episodes`, `tracks`, `sessions`, `transcript_segments`. Embeddings use OpenAI `text-embedding-3-small` (1536 dims). The RPC function is defined in `web/supabase/match_segments.sql`.

## Key Conventions

**Citations are mandatory**: every chatbot answer must include inline timestamps in `[YYYY-MM-DD @ HH:MM:SS]` format. If generation misses markers, append deterministic fallback citations from retrieved context.

**Tommy Vance persona**: the chatbot speaks in Tommy's voice. See `plans/TVpersonna.md` for tone guidelines. Concise answers, but never at the expense of factual grounding.

**Plan tracking**: phase plans in `plans/` use checkboxes (`- [ ]`). Mark each step `- [x]` immediately after it succeeds. If a step fails, leave unchecked and add a brief inline note.

**Mobile-first UI**: all components must work on mobile as well as desktop.

**JSON episode schema** enriched incrementally by pipeline steps:
```json
{
  "show": { "date": "YYYY-MM-DD" },
  "track_listing": [{ "artist": "", "track": "", "verified_timestamp": "" }],
  "transcript": [{ "start": 0.0, "end": 0.0, "text": "" }]
}
```

## Python Environment

- Runtime: Python 3.13
- Key packages: `faster-whisper`, `shazamio`, `supabase`, `openai`, `curl-cffi`, `beautifulsoup4`
- Whisper config: model `large-v3`, quantization `int8` (CPU-optimised)
