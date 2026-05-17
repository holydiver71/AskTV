## Plan: Phase 3 — Research UI

Build a Next.js-based Research UI for AskTV with two primary surfaces:

- A searchable 1980 registry (episodes, tracks, sessions)
- A retrieval-augmented (RAG) chatbot that answers questions with date/timestamp citations

The chatbot landing state must present `images/tommyvance.png` as the visual focal point with the query box directly beneath it on both desktop and mobile.

## Overview

Goals:

- Provide accurate, citation-backed answers in the format `[YYYY-MM-DD @ HH:MM:SS]`.
- Keep the registry usable when the chat provider is unavailable (HTTP 429 or other errors).
- Make the chat provider swap-out simple via a small provider abstraction.

## Project TODOs


## Phases & Work Items

### Phase 0 — Baseline & scope lock


- [x] Freeze acceptance criteria (registry search, Tommy persona, citation format, 429 handling, provider seam)
- [x] Target initial launch for the 1980 dataset only; UI is read-only (no auth/editor flows)
- [x] Hard UI rule: initial chat view must show the Tommy hero image above the query field

### Phase 1 — Frontend bootstrap (blocking)


- [x] Initialize project: Next.js (App Router) + TypeScript + Tailwind CSS
- [x] Add `shadcn/ui` primitives for inputs, cards, buttons, toasts
- [x] Add env validation for `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and server-only provider key
- [x] Create initial routes: `/`, `/registry`, `/chat`, and API endpoints under `/api/chat`

### Phase 2 — Data & retrieval plumbing


- [x] Implement a typed Supabase client wrapper for server/browser contexts
- [x] Build registry queries (filters, pagination) for episodes, tracks, and transcript snippets
- [x] Implement retrieval: embed query → vector search → assemble grounded context blocks with `date` and `start` time metadata
- [x] Add a citation formatter utility that produces `[YYYY-MM-DD @ HH:MM:SS]` strings

### Phase 3 — Registry view


- [x] Build registry list and episode detail pages with compact cards and key timestamps
- [x] Ensure loading, empty, and error states so registry remains usable independent of chat

### Phase 4 — Chat API & provider abstraction


- [x] Define a provider interface: `generateAnswer(prompt, context)` and `embedQuery(text)`
- [x] Implement server API handler that validates input, runs retrieval, calls provider, enforces citation inclusion, and returns answer + cited segments
- [x] Map provider errors to clear client codes (including 429 handling)

### Phase 5 — Chat UI (Tommy-first hero)


- [x] Build chat first-view composition with centered `images/tommyvance.png`, heading, and query input beneath
- [x] Implement transition to conversation layout while keeping a compact Tommy identity in the header
- [x] Render responses with citation chips linking to registry filters (or copy timestamp behavior)
- [x] Add clear 429 UX: friendly temporary-unavailable copy and retry

### Phase 6 — UX polish & accessibility


- [x] Define design tokens (colors, typography, spacing)
- [x] Add subtle motion for hero reveal and citation appearance; respect reduced-motion preferences
- [x] Run accessibility checks: keyboard flow, ARIA labels, contrast ratios, focus order (image → input → submit)

### Phase 7 — Verification & launch readiness


- [x] Unit tests: citation formatting, time conversions, retrieval shaping
- [x] Integration tests: API 200/400/429/500 behaviour, provider timeouts
- [x] UI tests: responsive assertion that hero image appears above input at standard breakpoints
- [x] Mobile QA: verify chat and registry usability on phone-sized viewports (e.g., 360x800 and 390x844), including tap targets, readable text, and no horizontal scrolling *(headless Playwright audit completed at both viewports; tap targets adjusted to >=44px where needed)*
- [x] Manual validation: 10+ known prompts checked for correct citation output *(14 prompts checked; 12 returned citation-marked answers, 2 returned explicit no-context response)*
- [x] Document runbook: environment variables, local start, provider swap, and failure modes

## Current status snapshot (17 May 2026)

- Implemented and build-verified: Phases 0-6 are complete.
- Completed verification so far: production `npm run build` passes (compile + typecheck + route generation), Phase 7 automated suite passes, mobile viewport QA completed, and 10+ prompt manual citation validation completed.
- Remaining before launch: optional quality improvement for broad aggregate questions that currently return the explicit no-context fallback.

## Relevant files

- `plans/AskTV.plan.md` — canonical Phase 3 requirements and guardrails
- `plans/phase3.md` — this detailed plan
- `README.md` — project overview and frontend stack
- `images/tommyvance.png` — mandatory hero asset for the chat screen
- `scripts/migrate_schema.sql` — DB schema reference for typed client contracts
- `scripts/upload_episodes.py` — data shape reference used by registry/retrieval

## Verification checklist

1. Lint + typecheck + tests pass for UI and API layers.
2. Responsive UI tests confirm hero image appears before the query input on mobile and desktop.
3. API tests verify graceful 429 handling and that registry routes remain functional when chat fails.
4. Manual: verify 10+ known-answer queries include `[YYYY-MM-DD @ HH:MM:SS]` citations.

## Decisions & scope

- Included: Phase 3 UI, chat grounding, citation enforcement, 429 UX, and provider abstraction.
- Excluded: auth, billing, donations, multi-year expansion, and audio hosting.
- Non-negotiable: Tommy hero image front-and-centre with the query box directly beneath on initial chat screen.

## Considerations

- Decide whether the hero collapses to an avatar after the first message or remains as a medium portrait in the header.
- Decide citation click behavior early (copy vs open registry-filtered view).
- Define Tommy persona length/style policy (concise vs broadcast) to align prompt engineering and UI truncation.