# Plan: Phase 2 — The Knowledge Base (Supabase)

Upload and vectorise the 1980 archive into Supabase so it can be queried by the Phase 3 chatbot. Uses 512-dim embeddings to stay within the free tier for the full 1978–1993 archive.

---

## Phase 2A: Manual Setup — Supabase Project

- [x] 1. Go to [supabase.com](https://supabase.com) → create a free account → **New Project**
- [x] 2. Note down three values from **Project Settings → API**:
   - `Project URL` (e.g. `https://xxxx.supabase.co`)
   - `anon / public` key
   - `service_role` key (keep this secret — used for server-side writes)
- [x] 3. In the Supabase **SQL Editor**, run: `CREATE EXTENSION IF NOT EXISTS vector;`
   Confirm `pgvector` appears in **Database → Extensions**

---

## Phase 2B: Manual Setup — OpenAI API Key

- [x] 4. Go to [platform.openai.com](https://platform.openai.com) → create account → **API Keys → Create new key**
- [x] 5. Add a small credit balance ($5 minimum) under **Billing**

---

## Phase 2C: Local Environment Setup

- [x] 6. Create `.env` in the workspace root with:
   ```
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SERVICE_KEY=your_service_role_key
   OPENAI_API_KEY=sk-...
   ```
   Add `.env` to `.gitignore` immediately.
 - [x] 7. Run: `pip install openai supabase` and update `requirements.txt`

---

## Phase 2D: Schema Migration — Run SQL (manual, one-time)

- [x] 8. Write `scripts/migrate_schema.sql` with the following tables:
   - `episodes` — `id uuid PK`, `date date UNIQUE`, `title text`, `url text`, `comments text[]`
   - `sessions` — `id uuid PK`, `episode_id uuid FK → episodes`, `artist text`, `details text`, `position smallint`
   - `tracks` — `id uuid PK`, `episode_id uuid FK → episodes`, `artist text`, `track text`, `details text`, `verified_timestamp float8`, `position smallint`
   - `transcript_segments` — `id uuid PK`, `episode_id uuid FK → episodes`, `chunk_start float8`, `chunk_end float8`, `text text`, `embedding vector(512)`
   - HNSW index on `transcript_segments(embedding)` for fast similarity search
- [x] 9. Paste `migrate_schema.sql` into Supabase SQL Editor and run it. Confirm all four tables appear in **Table Editor**.

---

## Phase 2E: Write `scripts/upload_episodes.py`

- [x] 10. Script reads all `data/episodes/1980/*.json` and upserts to Supabase:
   - `episodes` row from `title`, `url`, `show.date`, `show.comments`
   - `sessions` rows from `sessions[]`, preserving list order as `position`
   - `tracks` rows from `track_listing[]`, preserving order, including `verified_timestamp` where present
   - `transcript_segments` rows (text + timestamps only, **no embeddings yet**) — groups consecutive non-music segments into ~60-second windows; skips `[Music]` and `[redacted address]` segments
   - Uses `upsert` with `on_conflict=date` so re-runs are safe and idempotent
   - Logs to `logs/upload_episodes.log`
- [x] 11. Run the script and verify row counts in Supabase Table Editor:
   - `episodes`: 49 rows
   - `tracks`: ~866 rows
   - `sessions`: ~147 rows

*This step is independent of OpenAI — verify relational data before spending any API credits.*

---

## Phase 2F: Write `scripts/vectorise_transcripts.py`

- [x] 12. Script queries Supabase for all `transcript_segments` where `embedding IS NULL`
- [x] 13. For each chunk, generates an embedding via OpenAI `text-embedding-3-small` with `dimensions=512`:
    - Text sent to API is prefixed with episode context: `"Friday Rock Show {date}: {chunk_text}"`
    - Batches requests (up to 100 at a time) to minimise API calls and cost
    - Updates the `embedding` column for each processed row
    - Skips already-embedded rows — safe to resume after interruption
    - Logs progress and cost estimate to `logs/vectorise.log`
- [x] 14. Run the script. Confirm no NULL embeddings remain in `transcript_segments`.

*Safe to re-run for future years — processes anything with a NULL embedding.*

---

## Phase 2G: Verification (manual)

- [x] 15. Run a test similarity query in the Supabase SQL Editor to confirm vector search works:
    ```sql
    SELECT e.date, ts.text, ts.chunk_start
    FROM transcript_segments ts
    JOIN episodes e ON e.id = ts.episode_id
    ORDER BY ts.embedding <=> (
        SELECT embedding FROM transcript_segments LIMIT 1
    )
    LIMIT 5;
    ```
- [x] 16. Update `plans/AskTV.plan.md` Phase 2 section to mark all steps complete.

---

## Phase 2H: Quota & Cost Guardrails (consider before going public)

- [x] 17. In OpenAI **Settings → Limits**, set a **monthly spend cap** ($5 to start) and a notification alert threshold


---

## Phase 2I: Funding & Sustainability (optional)

- [ ] 21. Add unobtrusive donation options on the site (low-friction):
   - **Buy Me a Coffee / Ko-fi**: one-off donations; add a button on the chat and episode pages.
   - **GitHub Sponsors / Open Collective**: recurring sponsorship for small recurring revenue.

- [ ] 22. Membership / recurring support:
   - **Patreon**: tiered benefits (thank-you credit, early access, supporter-only RSS) — useful if you plan extra features.
   - **Paid tier**: small monthly fee for higher-rate limits or extended history (requires simple auth + billing integration).

- [ ] 23. Ads & affiliate (low priority for launch):
   - **AdSense / contextual ads**: only if traffic justifies it; requires privacy policy and approval.
   - **Affiliate links / merch**: link to relevant merch or playlists (low-effort revenue).

- [ ] 24. Grants / sponsorships (one-off, higher effort):
   - Apply for cultural heritage or music-archive grants; approach community partners or radio heritage organisations for sponsorship.

- [ ] 25. Implementation notes:
   - Start with a **donation button** (Ko-fi/Buy Me a Coffee) — least friction and no approval process.
   - Display Patreon/GitHub Sponsors only after you have consistent visitors.
   - Keep the Paywall/ads optional — do not block access to the core archive.

---

## Relevant Files

- `plans/AskTV.plan.md` — master plan, Phase 2 section to update as steps complete
- `scripts/migrate_schema.sql` — to create (new)
- `scripts/upload_episodes.py` — to create (new)
- `scripts/vectorise_transcripts.py` — to create (new)
- `requirements.txt` — add `openai`, `supabase`
- `.gitignore` — ensure `.env` is excluded

---

## Key Decisions

- **512-dim embeddings** chosen over 1536 to fit the full 1978–1993 archive within Supabase free tier (~80MB vs ~240MB for vectors)
- **`service_role` key** used for server-side writes (bypasses row-level security); `anon` key reserved for the Phase 3 frontend
- **Upload (2E) and vectorisation (2F) are separate scripts** — allows verifying relational data before spending OpenAI credits
- **Embedding text includes episode date** as context prefix for better retrieval relevance
- **`[Music]` and `[redacted address]` segments excluded** from embedding — no useful retrieval content
