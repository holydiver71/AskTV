# 📖 Project Spec: The Friday Rock Show Archive

## 1. Mission Statement
To build a high-fidelity, searchable digital index of Tommy Vance’s *Friday Rock Show*. The project focuses on **Information Retrieval (IR)**—turning decades of audio into a "Librarian" AI that can provide specific citations, tracklists, and historical context without the legal or technical overhead of hosting music.

---

## 2. Project Status: COMPLETED ✅
The foundation of the 1980 archive has been established.

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
### Step C: The privacy pass
* **Objective**: Tommy often reads out peoples names and addresses, while this was ok in the 1980s, it's not a good idea for them to be in the transcripts. Keep peoples names, but redact any addresses in the transcript apart from BBC Studio address.
* **Logic**: Create a plan document for this logic and replace this section with that plan
---

## 4. Phase 2: The Knowledge Base (Supabase)
Prepare and upload the enriched 1980 data to the cloud.

### Step A: Schema Migration
* **Action**: Use Supabase to create tables for `episodes`, `tracks`, and `sessions`.
* **Vector Setup**: Enable `pgvector` and create a `transcript_segments` table with a vector column (1536 dimensions for OpenAI embeddings).

### Step B: The Vectorization & Upload Script
* **Logic**:
    1. Chunk the transcript into ~60-second segments.
    2. Generate embeddings for each chunk using the OpenAI API.
    3. Push the relational data (tracks/sessions) and vector data (transcripts) to Supabase.

---

## 5. Phase 3: The Research UI (Next.js)
Build the frontend registry and AI interface.

### Step A: The Registry View
* **Feature**: A searchable logbook of all 1980 episodes, tracks, and sessions.
* **Stack**: Next.js, Tailwind CSS, Shadcn/UI.

### Step B: The RAG Chatbot
* **Feature**: A chat interface that queries the Supabase vector store to answer questions about the 1980 shows.
* **Persona**: The AI should respond in the style of Tommy Vance.
* **Citations**: Every answer must provide a date and a timestamp (e.g., [1980-01-25 @ 00:45:10]).

---

## 6. Technical Instructions for Copilot
When executing scripts:
1. **File Matching**: Always match MP3 and JSON files by the `YYYY-MM-DD` date string.
2. **Error Handling**: Implement logging for failed transcriptions or Shazam mismatches.
3. **Efficiency**: Use `int8` quantization for Whisper to optimize for CPU processing.
