# 📖 Project Spec: The Friday Rock Show Archive

## 1. Mission Statement
To build a high-fidelity, searchable digital index of Tommy Vance’s *Friday Rock Show*. The project focuses on **Information Retrieval (IR)**—turning decades of audio into a "Librarian" AI that can provide specific citations, tracklists, and historical context without the legal or technical overhead of hosting music.

---

## 2. Project Status: Phase 1 COMPLETED ✅
The full Phase 1 pipeline for the 1980 archive has been completed.

* **Phase 1: Ingestion Engine (Step A)**
    * **Action**: 49 radio broadcasts for 1980 merged and standardized.
    * **Format**: 128kbps Mono MP3.
    * **Naming Convention**: `FRS YYYY-MM-DD_128kps.mp3`.
    * **Location**: `/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSAudio/128kbps/1980`.
* **Phase 1: Metadata Scraping (Step B)**
    * **Action**: Metadata (Sessions and Track Listings) scraped from Fandom Wiki.
    * **Format**: JSON.
    * **Location**: `/media/andy/DATA/Projects/The Friday Rock Show Registry/FRSEpisodeDetailExtractor/output/1980`.
* **Environment Setup**
    * **Tools**: Python 3, FFmpeg, `faster-whisper`, `shazamio`, `supabase`, `openai`.
* **Important Web Resources**
    * **Fandom Wiki**: https://fridayrockshow.fandom.com/wiki
    * **Episode Guide**: https://www.dawtrina.com/music/frs/checklist.html?fbclid=IwY2xjawRyhTBleHRuA2FlbQIxMQBzcnRjBmFwcF9pZBAyMjIwMzkxNzg4MjAwODkyAAEeiyTIzB8zfnwqr93Dpif7vYKMSTGizrdPOTApWIsHzTR4OIudtNe7czZiBig_aem_u3RNl1-iZVDQN6xfy4Wccw
    * **Facebook**: https://www.facebook.com/groups/170443413007183

---

## 3. Phase 1: The Local Processing Factory (Next Steps)
The following steps must be executed locally to enrich the existing JSON files with audio-derived data.

### Step A: The Transcription Engine
* **Objective**: Convert spoken word to timestamped text to capture Tommy Vance's introductions and commentary.
* **Input**: `FRS YYYY-MM-DD_128kps.mp3`.
* **Tool**: `faster-whisper` (Model: `large-v3`, Quantization: `int8`).
* **Requirement**: Iterate through the 1980 audio folder, matching each MP3 to its corresponding JSON file.
* **Output**: Append a `transcript` array to the JSON file with objects containing `start`, `end`, and `text`.    * **Next**: Immediately after this step completes, run **Phase 1** of `plans/transcribe-clean-plan.md` (ellipsis/silence stripping — no dependencies).
### Step B: The Music Indexer (Validation Pass)
* **Objective**: Use audio fingerprinting to verify and timestamp the "Track Listing" found in the scraped JSON.
* **Input**: `FRS YYYY-MM-DD_128kps.mp3`.
* **Tool**: `ShazamIO`.
* **Logic**:
    1. Sample 15-second probes every 180 seconds.
    2. Cross-reference Shazam results against the `official_tracklist` in the JSON.
    3. If a match is found, update the JSON with the precise `verified_timestamp`.
    * **Next**: Once `verified_timestamp` fields are written, run **Phase 2** of `plans/transcribe-clean-plan.md` (lyrical muzzling — requires Shazam timestamps).
### Step C: The Privacy Pass ✅
* **Objective**: Tommy often reads out people's names and addresses. While acceptable in the 1980s, specific addresses should not appear in the transcripts.
* **Completed**:
    * `scripts/redact_addresses.py` written and run across all 49 episodes.
    * **106 redactions** applied — house numbers and street names replaced with `[redacted address]`.
    * Area / region / town information preserved (e.g. "Sutton Coldfield in the West Midlands" kept).
    * Multi-segment addresses handled (e.g. where street name bleeds across two transcript tags).
    * BBC Radio 1, London, W1A4WW (broadcaster address) explicitly preserved.
    * Supports `--dry-run` for safe previewing.
---

## 4. Phase 2: The Knowledge Base (Supabase) — COMPLETED ✅
Prepare and upload the enriched 1980 data to the cloud. Full step-by-step plan: `plans/phase2.md`.

### Step A: Manual Setup ✅
* Supabase project created (`AskTV`, West EU / Ireland region)
* `pgvector` extension enabled
* Project URL, anon key, service_role key noted; `.env` placeholders created

### Step B: OpenAI Setup ✅
* Create API key at platform.openai.com; add $5 credit; set $5 monthly spend cap

### Step C: Schema Migration ✅
* Write and run `scripts/migrate_schema.sql` — creates `episodes`, `sessions`, `tracks`, `transcript_segments` tables
* `transcript_segments` uses `vector(512)` — 512-dim embeddings chosen to keep full 1978–1993 archive within Supabase free tier (~80MB vs ~240MB at 1536-dim)
* HNSW index on `embedding` column for fast similarity search

### Step D: Upload Script ✅
* `scripts/upload_episodes.py` — upserts all relational data from JSON files; groups transcript segments into ~60s chunks; skips `[Music]` and `[redacted address]` segments; idempotent upsert on episode date

### Step E: Vectorisation Script ✅
* `scripts/vectorise_transcripts.py` — generates 512-dim embeddings via OpenAI `text-embedding-3-small`; batches 100 at a time; skips already-embedded rows; resumable

### Step F: Verification ✅
* Row counts confirmed (49 episodes, ~866 tracks, ~147 sessions); similarity query returning relevant results — vector search operational

### Step G: Cost & Quota Guardrails (before going public)
* OpenAI monthly spend cap set; Phase 3 frontend handles HTTP 429 gracefully; non-AI features remain functional when chat is capped; consider Groq free tier as drop-in alternative if traffic grows

---

## 5. Phase 3: The Research UI (Next.js)
Build the frontend registry and AI interface.

### Step A: The Registry View
* **Feature**: A searchable logbook of all 1980 episodes, tracks, and sessions.
* **Stack**: Next.js, Tailwind CSS, Shadcn/UI.

For the full, detailed Phase 3 execution plan see [plans/phase3.md](plans/phase3.md).

### Step B: The RAG Chatbot
* **Feature**: A chat interface that queries the Supabase vector store to answer questions about the 1980 shows.
* **Persona**: The AI should respond in the style of Tommy Vance.
* **Citations**: Every answer must provide a date and a timestamp (e.g., [1980-01-25 @ 00:45:10]).

### Step C: Pre-launch Guardrails
* **Purpose**: Ensure stability, user experience and cost control before the public launch of the chat feature.
    - [ ] **Frontend: HTTP 429 handling** — Wrap chatbot API calls to catch HTTP 429 (quota exceeded) and display a friendly message (e.g. "The Ask Tommy feature is temporarily unavailable — please try again later").
    - [ ] **Resilience: Non-AI independence** — Ensure episode browser, track listings, and search work independently of OpenAI so core features remain available when chat is down.
    - [ ] **Scale alternative: Provider swap** — Keep backend abstraction so swapping to a different provider (e.g. Groq) is straightforward if traffic or cost requires it.
 

---

## 6. Technical Instructions for Copilot
When executing scripts:
1. **File Matching**: Always match MP3 and JSON files by the `YYYY-MM-DD` date string.
2. **Error Handling**: Implement logging for failed transcriptions or Shazam mismatches.
3. **Efficiency**: Use `int8` quantization for Whisper to optimize for CPU processing.
