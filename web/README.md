# AskTV Web (Phase 3)

Next.js frontend for The Friday Rock Show Archive research interface.

## Environment

Copy `.env.example` to `.env.local` and configure:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `OPENAI_API_KEY`

## Local Development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Testing (Phase 7)

```bash
npm run test:run
```

Includes:

- Unit tests for citation formatting and retrieval context shaping
- Integration tests for `/api/chat` success/error handling (200/400/429/500 + provider timeout)
- UI tests validating chat first-view hero/input ordering on desktop and mobile widths

## Runbook

See `docs/phase7-runbook.md` for launch-readiness checks, provider swap notes, and failure-mode handling.
