## Plan: Phase 3 Research UI

Build a new Next.js-based Research UI for AskTV that ships two core surfaces: a searchable 1980 registry and a Tommy Vance-centered chat experience. The chatbot landing state will place the Tommy image as the visual focal point, with the query box directly underneath on both desktop and mobile. The implementation will prioritize retrieval accuracy (citations with timestamps), graceful quota handling, and UI resilience so non-AI browsing continues if chat is unavailable.

**Steps**
1. Phase 0: Baseline and scope lock
1. Confirm Phase 3 scope from planning artifacts and freeze acceptance criteria: registry search, chat persona, citation format, HTTP 429 handling, and provider abstraction.
1. Define hard UI requirement: on chatbot screen, images/tommyvance.png centered and prominent above the query field (first-view layout, before any messages).
1. Decide launch boundary: 1980-only dataset and read-only public UI (no auth, no editing workflows) to keep this phase focused.

1. Phase 1: Frontend bootstrap (blocks all later steps)
1. Initialize Next.js App Router project with TypeScript, Tailwind, and base lint/test tooling.
1. Add shadcn/ui primitives needed for inputs, cards, buttons, badges, sheets, and toast alerts.
1. Add environment variable schema and startup validation for public Supabase URL/anon key and server-only OpenAI key.
1. Establish route skeleton: home/registry, chat, and API route handlers.

1. Phase 2: Data access layer and retrieval plumbing (parallelizable after Phase 1)
1. Build a typed Supabase client wrapper for server and browser contexts.
1. Implement registry queries for episodes, sessions, tracks, and transcript snippets with pagination and keyword filtering.
1. Implement retrieval service that converts user question to embedding, fetches nearest transcript segments, and composes grounded context blocks with date/start time metadata.
1. Define citation formatter that emits exact answer references in [YYYY-MM-DD @ HH:MM:SS] format.

1. Phase 3: Registry view (parallel with Phase 4 once shared data layer exists)
1. Build registry page shell with quick filters (date, artist, track/session text) and result sections.
1. Implement compact episode cards linking to expanded metadata and key timestamps.
1. Add loading/empty/error states so registry remains fully usable independent of chat API status.

1. Phase 4: Chat API contract and provider abstraction (depends on Phase 2)
1. Create a provider interface (generateAnswer, embedQuery) so OpenAI can be swapped later (e.g., Groq adapter) without UI rewrite.
1. Implement chat API endpoint that:
1. validates input,
1. runs retrieval,
1. prompts model in Tommy Vance style while requiring grounded output,
1. enforces citation inclusion,
1. returns answer + cited segments + latency metadata.
1. Add robust error mapping for 429, timeout, provider/network, and validation failures.

1. Phase 5: Chat UI with Tommy-first hero layout (depends on Phase 1 and Phase 4)
1. Build chat page first-view composition:
1. centered images/tommyvance.png hero image,
1. short identity heading/subheading,
1. query box directly beneath image,
1. optional suggested prompts under query input.
1. Preserve Tommy-first composition until first successful user query; after that, transition to conversation layout while keeping image visible in compact form near chat header.
1. Implement streaming or staged response rendering with clear citation chips linking to source dates/times.
1. Add explicit 429 UX message: Ask Tommy temporarily unavailable; retain registry navigation and allow retry later.
1. Ensure mobile behavior: image remains above query field with responsive sizing and no overlap/jank.

1. Phase 6: UX polish, accessibility, and visual direction (depends on Phase 3 and Phase 5)
1. Define design tokens (color, typography, spacing, elevation) with a non-generic editorial rock-archive identity.
1. Add meaningful motion only: first-load hero reveal and subtle stagger for citations/results.
1. Run accessibility checks for contrast, keyboard flow, focus order (image to input to submit), aria labels, and reduced-motion support.
1. Add metadata/SEO and social preview image for shareable chat/registry routes.

1. Phase 7: Verification and launch readiness (depends on all phases)
1. Add unit tests for citation formatting, timestamp conversion, and retrieval result shaping.
1. Add integration tests for API status handling (200/400/429/500), including provider timeout simulation.
1. Add UI tests for chatbot first-view contract: Tommy image centered and query input beneath on desktop and mobile breakpoints.
1. Run manual smoke checks across Chromium and Firefox for layout, filtering, chat response quality, and citation correctness.
1. Document runbook: env setup, local run commands, known failure modes, and provider swap steps.

**Relevant files**
- /media/andy/DATA/Projects/The Friday Rock Show Registry/AskTV/plans/AskTV.plan.md — canonical project spec where Phase 3 acceptance criteria originate
- /media/andy/DATA/Projects/The Friday Rock Show Registry/AskTV/README.md — project overview and stack alignment for frontend scope
- /media/andy/DATA/Projects/The Friday Rock Show Registry/AskTV/images/tommyvance.png — mandatory hero asset for chatbot screen composition
- /media/andy/DATA/Projects/The Friday Rock Show Registry/AskTV/scripts/migrate_schema.sql — source of database shape to mirror in typed frontend data contracts
- /media/andy/DATA/Projects/The Friday Rock Show Registry/AskTV/scripts/upload_episodes.py — reference for expected data fields used by registry/chat retrieval

**Verification**
1. Automated: lint + type-check + test suite pass for UI and API layers.
1. Automated: dedicated responsive tests prove chatbot first-view order is image then input at mobile and desktop breakpoints.
1. Automated: API tests confirm 429 returns user-safe error contract and does not break non-chat routes.
1. Manual: ask at least 10 known-answer prompts and verify every response contains one or more [YYYY-MM-DD @ HH:MM:SS] citations.
1. Manual: disable OpenAI key or force 429 and confirm registry/search still works while chat shows friendly temporary-unavailable message.

**Decisions**
- Included scope: Phase 3A/3B UI delivery, 429 guardrail UX, provider abstraction seam, and citation enforcement.
- Excluded scope: auth, billing, donations, year expansion beyond 1980, and audio playback hosting.
- Core UX decision: Tommy image is front-and-centre in initial chat state with query box directly beneath; this is a non-negotiable acceptance criterion.

**Further Considerations**
1. Recommendation: decide whether first-chat transition should collapse the image to a small avatar or keep a medium portrait in the chat header for stronger brand continuity.
2. Recommendation: define citation click behavior early (copy timestamp vs open registry-filtered view) to avoid reworking chat message components later.
3. Recommendation: set a response-length policy for Tommy persona (concise vs broadcast-style) so prompt and UI truncation rules stay aligned.