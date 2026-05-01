# Shomery — Customer-Facing Web App

> **Read this first.** Canonical project brief — invariants, hard rules, where to find detail. If anything in any other doc contradicts this file, this file wins.

## What Shomery is

Private "NotebookLM for your inbox." Watches Gmail for senders/domains the user specifies, summarizes each email with a local LLM, saves the `.md` to the user's own Drive folder, lets the user ask grounded questions about any subject. Answers come only from the user's own corpus; the assistant refuses if the answer isn't there.

Target: SMBs, Korea-leaning at launch, global afterward. Brand: Apple-clean, white canvas, single Emerald accent. Working name was "Pipelane" — final brand is **Shomery**.

## How it fits

Customer-facing PWA inside the `email2ppt` monorepo. Backend Python pipeline (watcher, RAG, channel adapters) is unchanged. Same Firebase project, separate Hosting site, shared Firestore.

```
email2ppt/
├── watcher.py, bridge.py, ...    Python pipeline (do not modify from this app)
├── apps/
│   ├── email2ppt-portal/          existing admin/setup
│   └── shomery-web/               ← THIS APP
└── shared/types/                  shared via @shomery/shared-types
```

## Tech stack

Next.js 14 (App Router) + TypeScript strict + Tailwind + shadcn/ui + Firebase (Auth, Firestore, Storage, Hosting) + `next-intl` (en, ko, pt-BR). Light mode only in v1.

## Brand essentials

| | Value |
|---|---|
| Accent | Emerald `#10B981` |
| Hover | `#059669` |
| Tint | `#ECFDF5` |
| Ink / soft / paper | `#111111` / `#6B7280` / `#FFFFFF` |
| Warning (priority) | Amber `#F59E0B` |
| Type | Inter, Regular (400) + Bold (700) only |
| Motif | 3px Emerald left border on summaries and hero cards |
| Mode | Light only (v1) |

Voice, banned words, channel-icon colors, full motif rules → `docs/brand.md`.

## Hard rules

Non-negotiable. Apply to every line of code and copy.

1. **No `firebase-admin` in `src/`.** Web app uses Firebase client SDK only. Admin ops live in Cloud Functions or the Python backend. CI greps for this.
2. **No direct LLM calls from the client.** All RAG queries go through `POST /api/rag/answer` → Python orchestrator's `rag_service.answer()`.
3. **Markdown is canonical.** Watcher writes `.md`; PDF is rendered on demand. Pre-Drive-verification, `.md` lives in Firebase Storage at `summaries/{uid}/{subject_slug}/{email_id}.md`. Reads go through one helper so the Drive swap is one function change.
4. **Subject groups are virtual.** Combining subjects does NOT move emails. Group is a parent reference; ungrouping is risk-free. A subject is in zero or one groups, not multiple.
5. **NotebookLM-mode RAG is scoped.** Per-subject and per-group queries add `where subject_slug IN (...)` to retrieval. Refusal phrasing reflects scope.
6. **Telegram is opt-in, never default.** Email digest is the default notification channel.
7. **Brand green is for the brand, not for status.** Use Amber `#F59E0B` for high-priority highlights, gray for muted/read.
8. **No dark UI surfaces in v1.** Light canvas only.
9. **All user-facing strings live in `messages/{locale}.json`.** The `react/jsx-no-literals` ESLint rule rejects raw JSX text.
10. **All schema-typed reads use `@shomery/shared-types`.** When schema drifts, compile breaks before runtime does.
11. **No Drive code until Google OAuth Drive write verification is in flight.** Use the Storage seam in the meantime.
12. **No KMS / log-redaction / GDPR-cleanup / retention-sweep changes from this app.** Those compliance modules are Python-side only.
13. **Validate every web → Python boundary with a Pydantic model.** Any payload the web sends to a Python service is validated against a Pydantic schema on the backend before downstream code touches it. Boundary validation is what lets the rest of the pipeline trust its inputs.
14. **No secrets in `NEXT_PUBLIC_*` env vars.** Anything `NEXT_PUBLIC_*` is shipped to the browser. The Firebase Web SDK config (apiKey, authDomain, projectId, etc.) is public by design — security comes from Firestore rules + App Check. Third-party API keys (KakaoTalk, WhatsApp, SMS, Twilio, OpenAI, etc.) are NOT public — they live in Cloud Functions secrets, never in client-accessible env vars.
15. **Cloud Functions must go through `firestore_*.py` wrappers when touching pipeline-written collections.** The wrappers handle KMS envelope encryption, audit logging, and log redaction. Bypassing them with raw admin-SDK calls drops the user's encryption envelope and leaves an audit-log gap.

The *why* behind each rule and the broader decision history → `docs/decisions.md`.

## v1 scope

Routes (all locale-prefixed):

- `/[locale]/sign-in` — Google OAuth, single button.
- `/[locale]/onboarding/{welcome,step-1,step-2,step-3}` — mobile-first 3-step setup.
- `/[locale]/feed` — chronological list of processed emails (real-time).
- `/[locale]/subjects` + `/[locale]/subjects/{slug}` + `/[locale]/groups/{id}` — sidebar + detail.
- `/[locale]/subjects/{slug}/ask` + `/[locale]/groups/{id}/ask` + `/[locale]/ask` — NotebookLM-mode chat.
- `/[locale]/settings` — Inbox / Watch list / Save location / Notifications / Privacy.

Per-screen detail lives in per-PR plans. The original SCREENS_SPEC.md is archived at `docs/_archive/SCREENS_SPEC.md` for reference.

## Data model

`Subject`, `Group`, `EmailSummary`, `ChannelConfig` — TypeScript definitions in `shared/types/`. The typed source is canonical; older docs that show literal Firestore paths are illustrative.

Full walkthrough → `docs/data-model.md`.

## What's deferred

Drive integration (gated on OAuth verification), KakaoTalk/WhatsApp/SMS adapters (one at a time post-launch), multi-tag subject membership, native mobile apps, dark mode, public REST API, Slack adapter, team accounts, white-label.

## External lead times

- Google OAuth Drive write verification — 4–8 weeks. Open ticket Day 1.
- KakaoTalk Bot business registration — 1–2 weeks once 사업자등록증 in hand.
- `shomery.com` domain + trademark search — same day.

## When in doubt

| Topic | Where |
|---|---|
| Brand voice, banned words, full color use | `docs/brand.md` |
| *Why* a decision was made | `docs/decisions.md` |
| Data model detail | `docs/data-model.md` |
| Phased build sequencing (historical) | `docs/_archive/IMPLEMENTATION_PLAN.md` |
| Per-screen UX (historical) | `docs/_archive/SCREENS_SPEC.md` |
| Anything not above | Ask the product owner before assuming |

When this file is silent on something, prefer asking over guessing. When old code or comments contradict this file, this file wins.
