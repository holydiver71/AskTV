<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Application Architecture (Concise)
- **App style**: Vertical-slice Next.js App Router app with clear boundaries between UI, API routes, and domain logic.
- **Flow**: `app/chat` UI -> `app/api/chat/route.ts` orchestration -> `lib/ai/*` provider calls + `lib/db/retrieval.ts` search -> JSON response with grounded citations.
- **Data model**: Supabase/Postgres is the source of truth for episodes, tracks, sessions, and transcript segments.
- **IR-first behaviour**: Answers must be retrieval-grounded and include inline citations in `[YYYY-MM-DD @ HH:MM:SS]` format.

## Tech Stack (Current)
- **Framework**: Next.js 16 (App Router), React 19, TypeScript.
- **Styling/UI**: Tailwind CSS 4, shadcn/ui primitives, utility composition via `clsx` + `tailwind-merge`.
- **Backend services**: Supabase (`@supabase/supabase-js`, `@supabase/ssr`) for data and vector RPC retrieval.
- **AI**: OpenAI SDK for embeddings (`text-embedding-3-small`) and grounded generation.
- **Validation**: Zod for request and environment schema validation.
- **Testing**: Vitest + Testing Library for unit/integration; Playwright for UI flows.

## Design Patterns To Follow
- **Thin route handlers**: Parse/validate input, coordinate services, map errors to stable API error codes.
- **Provider abstraction**: Keep model-specific logic in `lib/ai/*`; call through typed provider interfaces.
- **Schema-first contracts**: Validate all external input with Zod (`request`, `env`, and integration payloads).
- **Utility purity**: Keep formatting/extraction helpers pure and deterministic (no hidden network/file side effects).
- **Compatibility shims**: Preserve graceful fallbacks for known deployment drift (for example, legacy RPC signatures).
- **Server/client separation**: Keep secrets and privileged logic on the server; import server-only modules from server contexts only.
- **Citation safety net**: If generation misses citation markers, append deterministic fallback citations from retrieved context.
- **Mobile First**: All UI functionality must work in a mobile phone as well as a laptop pc

## Practical Guardrails
- Prefer additive changes over broad refactors unless required.
- Keep user-facing failures friendly and actionable (`invalid_request`, `retrieval_not_configured`, `provider_timeout`, etc.).
- Maintain concise responses in the Tommy voice, but never at the expense of factual grounding.
