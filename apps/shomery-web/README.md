# Shomery — Web App

A private "NotebookLM for your inbox." Customer-facing PWA that surfaces email summaries from email2ppt's Python pipeline and lets users ask grounded questions about their own corpus.

> **Read [CLAUDE.md](./CLAUDE.md) first.** It is the canonical project brief — brand, architecture, decisions, things-not-to-do. If anything in this README contradicts CLAUDE.md, CLAUDE.md wins.

## Where this lives

This app sits inside the `email2ppt` monorepo at `apps/shomery-web/`. The Python pipeline (watcher, RAG orchestrator, channel adapters) lives in the repo root. Shared TypeScript types live in `../../shared/types/` and are consumed via the workspace package `@shomery/shared-types`.

## Stack

Next.js 14 (App Router) + TypeScript (strict) + Tailwind + shadcn/ui + Firebase (Auth, Firestore, Storage, Hosting) + `next-intl` (en, ko, pt-BR). Light mode only in v1.

## Quick start

All commands run from the **monorepo root** unless noted.

```bash
pnpm install
pnpm shomery:dev          # Next.js on http://localhost:3000 → redirects to /en/sign-in

# In a separate shell, from apps/shomery-web/, start the Firebase emulators:
firebase emulators:start --project demo-shomery
```

Required environment variables (`apps/shomery-web/.env.local`):

```
NEXT_PUBLIC_FIREBASE_API_KEY=
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=
NEXT_PUBLIC_FIREBASE_PROJECT_ID=
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=
NEXT_PUBLIC_FIREBASE_APP_ID=
NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true   # unset/false in production
NEXT_PUBLIC_SENTRY_DSN=                  # leave empty to disable in dev
NEXT_PUBLIC_RAG_ENDPOINT=                # URL of the Python orchestrator (added when Ask UI lands)
```

The Firebase config values come from the new Web app registered under the existing `email2ppt` Firebase project. The project ID also goes in `.firebaserc` (currently `PLACEHOLDER_FIREBASE_PROJECT_ID`).

## Folder layout

```
apps/shomery-web/
├── CLAUDE.md                ← canonical project brief
├── README.md                ← this file
├── IMPLEMENTATION_PLAN.md   ← phased build plan (superseded by CLAUDE.md; see banner)
├── SCREENS_SPEC.md          ← per-screen UX detail (superseded by CLAUDE.md; see banner)
├── firebase.json            ← Hosting + emulator ports
├── firestore.rules          ← per-uid scoping; tested in tests/integration/
├── storage.rules            ← v1 markdown seam: summaries/{uid}/{slug}/{id}.md
├── messages/                ← next-intl translation bundles
│   ├── en.json
│   ├── ko.json
│   └── pt-BR.json
├── src/
│   ├── middleware.ts        ← next-intl locale middleware
│   ├── i18n/                ← routing config + request-side message loader
│   ├── app/
│   │   └── [locale]/        ← every user-facing route is locale-prefixed
│   │       ├── layout.tsx
│   │       ├── page.tsx     ← redirects to /[locale]/sign-in
│   │       └── sign-in/page.tsx
│   ├── components/ui/       ← shadcn/ui primitives (Button so far)
│   └── lib/
│       └── firebase/        ← client SDK init (Auth, Firestore, Storage, emulator wiring)
├── tests/
│   ├── unit/                ← Vitest + RTL
│   ├── integration/         ← @firebase/rules-unit-testing against the emulator
│   └── e2e/                 ← Playwright (chromium only, 3-locale smoke)
├── functions/               ← Cloud Functions (empty in v1)
└── public/
```

## Scripts

All from the monorepo root unless noted.

| Command | What it does |
|---|---|
| `pnpm shomery:dev` | Next.js dev server |
| `pnpm shomery:build` | Production build |
| `pnpm shomery:lint` | ESLint (jsx-a11y, no raw JSX text) |
| `pnpm shomery:typecheck` | `tsc --noEmit` |
| `pnpm shomery:test` | typecheck → lint → unit → e2e |
| `pnpm --filter shomery-web test:unit` | Vitest unit + coverage (≥70% on `src/**`) |
| `pnpm --filter shomery-web test:integration` | Firestore-rules tests (requires running emulator) |
| `pnpm --filter shomery-web test:rules` | Boots emulator, runs rules tests, tears down |
| `pnpm --filter shomery-web test:e2e` | Playwright across `/en`, `/ko`, `/pt-BR` |
| `pnpm --filter shomery-web emulators` | `firebase emulators:start` |

## Conventions

- **Brand color is Emerald `#10B981`.** Never use brand green for status indicators — Amber `#F59E0B` for high-priority highlights, gray for muted/read.
- **No dark mode in v1.** Light/bright canvas only.
- **All user-facing strings live in `messages/{locale}.json`.** The `react/jsx-no-literals` lint rule rejects raw JSX text.
- **No emoji in copy** unless reproducing a third-party UI surface (the Telegram bot card uses 📬 — match it where the channel-card is rendered).
- **All RAG queries go through the Python orchestrator** (`POST /api/rag/answer`) — no direct LLM calls from the client.
- **Firestore reads** are typed via `@shomery/shared-types`. When the schema drifts, the compile breaks before runtime does.
- **No `firebase-admin` in `src/`.** Use the Firebase client SDK only; admin operations live in Cloud Functions or the Python backend. CI greps for this.
- **Markdown is canonical.** Until Drive OAuth verification lands, `.md` content lives in Firebase Storage at `summaries/{uid}/{subject_slug}/{email_id}.md`. Reads go through one helper so the Drive swap is one function change.

## Status

Foundation merged: app boots, sign-in placeholder renders under all three locales, all quality gates green, Firestore + Storage rules verified against the emulator. Functional Google OAuth + read-only Feed are the next chunk. The phased plan in `IMPLEMENTATION_PLAN.md` is superseded by CLAUDE.md and per-PR plans, but remains a useful reference for sequencing.
