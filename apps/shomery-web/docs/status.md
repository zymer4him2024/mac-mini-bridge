# Shomery — Implementation Status

Per-screen status of what's merged vs. in-flight. **This file is changelog territory** — it changes faster than CLAUDE.md and should not be read for invariants. For canonical decisions, always go to CLAUDE.md.

## Onboarding

The flow is live and gates `/feed` and `/subjects/*`. A signed-in user without `users/{uid}.onboardingCompletedAt` is redirected to `/[locale]/onboarding`.

- **Welcome** — live.
- **Step 1: Connect Gmail** — informational placeholder. Gmail watching is owned by the Python pipeline out-of-band.
- **Step 2: Watched senders** — interactive. Writes `priorityWatchSenders` on `users/{uid}/config/main`. The only interactive step in v1.
- **Step 3: Where to save** — informational placeholder. The Drive picker is gated on OAuth verification.
- **"Start watching"** — sets `onboardingCompletedAt` on the user doc and routes to `/feed`.

## Settings

The page is reachable from the sidebar's Settings link.

- **Watched senders** — live. Writes `priorityWatchSenders` on `users/{uid}/config/main`.
- **Notifications** — live. Writes `digestEnabled`, `telegramEnabled`, `telegramChatId` on the same doc (rules allow that exact allowlist). Five channel rows render; only **Email digest** and **Telegram** are interactive in v1. KakaoTalk, WhatsApp, SMS render as disabled rows with a *Coming soon* badge.
- **Privacy & data** — live. **Export** reads identity + config + folders + items via the client SDK and downloads a JSON file (no Cloud Function needed). **Delete account** calls the `deleteAccount` Cloud Function (admin SDK), which recursive-deletes Firestore under `users/{uid}/**`, deletes Storage prefixes `summaries/{uid}/` and `pdfs/{uid}/`, and removes the Auth user.
- **Inbox** — ships in a dedicated PR.
- **Where to save** — ships in a dedicated PR (gated on Drive OAuth verification).

## Feed

Live. Renders `FolderItem` cards via collection-group query. The "Read full →" link opens the per-item markdown reader at `/[locale]/subjects/[slug]/items/[itemId]` when the item carries `markdownStoragePath`.

## Subjects

Live for browse. Selecting a subject opens a per-folder detail page. The per-item page renders `.md` via `getMarkdown(item)` — the single switch point for the future Drive backend.

The watcher does not yet emit `.md` blobs in production, so this path is exercised against fixtures in tests and renders an empty state for items without a `markdownStoragePath`.

**Deferred to dedicated PRs:** virtual groups, "+ New group" combine flow.

## Ask

Per-subject Ask is live. The subject detail header has an "Ask this subject" CTA that opens `/[locale]/subjects/[slug]/ask`, a NotebookLM-style split with a read-only `SourcesPanel` and an `AskPanel` that posts to the Python `rag_service` at `NEXT_PUBLIC_RAG_BASE_URL` with a Firebase ID token. The service runs on the Mac Mini against Ollama in v1; provider is swappable via `LLM_PROVIDER` on the backend.

**Deferred to follow-ups:** per-group Ask scoping (ships with virtual groups), global Ask, interactive Sources panel (per-item exclusion), and the cloud-LLM swap when Ollama is replaced.

## Foundation

Phase A merged. App boots, sign-in placeholder renders under all three locales, all quality gates green, Firestore + Storage rules verified against the emulator. Functional Google OAuth + read-only Feed are the next chunk per the most recent PR plan.
