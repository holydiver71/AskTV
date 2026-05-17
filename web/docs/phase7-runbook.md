# Phase 7 Runbook — Verification and Launch Readiness

## 1. Required Environment Variables

Set in `web/.env.local`:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `OPENAI_API_KEY`
- `ASKTV_CHAT_SYSTEM_PROMPT` (optional; override default Tommy persona/system prompt)

Validation is enforced in `lib/env.ts`.

## 2. Local Start

```bash
cd web
npm install
npm run dev
```

Open:

- Registry: `http://localhost:3000/registry`
- Chat: `http://localhost:3000/chat`

## 3. Automated Verification

Run all Phase 7 automated checks:

```bash
cd web
npm run test:run
```

Coverage intent:

- Citation formatting and extraction (`tests/unit/citations.test.ts`)
- Retrieval shaping (`tests/unit/context.test.ts`)
- Chat API behavior (`tests/integration/api-chat-route.test.ts`)
- First-view hero/input ordering (`tests/ui/chat-hero-layout.test.tsx`)

## 4. API Failure Modes

`POST /api/chat` maps errors as follows:

- `400 invalid_request`: malformed JSON or validation failure
- `429 quota_exceeded`: upstream quota exhausted
- `504 provider_timeout`: upstream timeout / abort
- `500 internal_error`: unexpected failures
- `503 retrieval_not_configured`: missing Supabase RPC function

## 5. Provider Swap Procedure

Current provider: `OpenAIProvider` (`lib/ai/openai-provider.ts`).

To swap providers:

1. Implement a new class that satisfies `AIProvider` in `lib/ai/provider.ts`.
2. Replace the provider import in `app/api/chat/route.ts`.
3. Keep `embedQuery` dimensions aligned with DB expectations (512-dim vectors today).
4. Run `npm run test:run`.

## 6. Mobile QA Checklist

Viewports:

- `360x800`
- `390x844`

Checklist:

- Chat hero portrait appears above the query box in first view
- Registry cards render without overlap
- No horizontal page scrolling on `/chat` and `/registry`
- Primary controls are easy to tap (target around 44px minimum)
- Body text remains readable without zooming

## 7. Manual Prompt Validation (10+ prompts)

Use `/chat` and verify each response includes citations in `[YYYY-MM-DD @ HH:MM:SS]` format and references plausible 1980 context.

Suggested prompts:

1. What AC/DC session did Tommy play in 1980?
2. When did Iron Maiden first appear on the Friday Rock Show in 1980?
3. What tracks did Motorhead have in 1980?
4. Which bands had BBC sessions in the first half of 1980?
5. Which 1980 broadcast mentioned Judas Priest?
6. Did Tommy reference Ozzy Osbourne in 1980 shows?
7. What did Tommy say around the start of the 1980-07-04 episode?
8. Which episodes include Black Sabbath tracks?
9. What were the key sessions in late 1980?
10. Which show had the most session entries?

Record outcomes in your release notes:

- Prompt
- Response citation(s)
- Pass/fail
- Notes

## 8. Latest Validation Snapshot

- Results log: `docs/phase7-validation-results.md`
