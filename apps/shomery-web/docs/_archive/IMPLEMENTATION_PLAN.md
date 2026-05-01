# Shomery — Implementation Plan

> **⚠ Superseded by [CLAUDE.md](./CLAUDE.md) and per-PR plans.** This document predates the locked-in CLAUDE.md decisions. Keep it as a reference for *phasing and sequencing* (Phase A → G, lead-time items, risks), but the specifics are stale in places — notably:
> - Routes are shown without the `/[locale]/` prefix; multi-locale (en, ko, pt-BR) is **v1**, not v1.5.
> - The auth route is `/sign-in`, not `/login`.
> - Firestore paths like `users/{uid}/emails`, `users/{uid}/onboarding`, `users/{uid}/excludedSources` are illustrative; the canonical schema lives in `shared/types/` and CLAUDE.md.
> - "Pipelane Bot" copy → "Shomery Bot."
> - The pre-Drive-verification storage seam is Firebase Storage at `summaries/{uid}/{slug}/{id}.md` (CLAUDE.md *Critical decisions* #1).
> - Phase A is **complete** as of the foundation PR (scaffold, locales, rules, tests).
>
> When this file disagrees with CLAUDE.md, CLAUDE.md wins.

A phased build plan for the customer-facing web app. Each phase ships something a real user could actually open and check.

## Sequencing constraints (non-negotiable)

These external lead times affect the plan and are outside our control. Start them Day 1 so they don't block the build later.

| Item | Lead time | What blocks until done |
|---|---|---|
| Google OAuth Drive write verification | 4–8 weeks | Phase E (Drive integration) |
| KakaoTalk Bot business registration | 1–2 weeks | KakaoTalk channel adapter (Phase F) |
| `shomery.com` domain registration + trademark check | Same day | OAuth redirect URIs, share links, email signatures |

## Phase A — Foundation (Week 1–2)

Goal: web app boots, user can sign in, lands on an empty feed.

- Scaffold Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui via `create-next-app`.
- Register a new Web app under the existing email2ppt Firebase project. Pull `firebaseConfig` into `.env.local`.
- Add a Hosting site `shomery-web` under the existing `email2ppt` Firebase project.
- Configure Firebase Emulator Suite locally (Auth + Firestore).
- Auth route: `/login` → Sign in with Google → redirect to `/feed`.
- Empty feed: *"We're watching for your first email. Tracked senders are listed in Settings."* with a button to Settings.
- Brand styles applied: Emerald `#10B981`, Inter, accent-edge motif, the no-shadow / 0.5px-border tokens.

**Done when:** A new user can sign in with Google at `shomery.web.app` and see the empty feed within 2 minutes of first tap.

## Phase B — Onboarding (Week 2–3)

Goal: a fresh user can complete the 3-step flow and reach the feed.

- `/onboarding/welcome` — brand mark + "Get started."
- `/onboarding/step-1` — Connect Gmail. Delegates to the existing email2ppt Gmail OAuth Cloud Function (don't duplicate that flow in the web app).
- `/onboarding/step-2` — Tracked senders/domains. Writes to `users/{uid}/priorityWatchSenders`.
- `/onboarding/step-3` — Drive folder picker. Show a placeholder "📁 My Drive / Shomery" with "Change" disabled. Real picker arrives in Phase E.
- Mobile-first layouts, working at 375px width.
- 3-dot progress indicator at the top of every step screen, primary CTA anchored at bottom.

**Done when:** A user goes welcome → step 1 → step 2 → step 3 → feed without errors. Onboarding state persisted in `users/{uid}/onboarding.complete = true`.

## Phase C — Feed + Subjects (Week 3–5)

Goal: user can browse processed emails, navigate subjects and groups.

- `/feed` — chronological list of `EmailSummary` cards. Real-time via `onSnapshot()` ordered by `received_at desc`, limit 50.
- `<EmailCard>` matches the Telegram bot layout: 📄 attachment chip + timestamp, 📬 sender, subject, 2–5 bullets, priority badge.
- `/subjects` — sidebar with grouped + ungrouped subjects, unread counts.
- `/subjects/{slug}` — selected subject view: rendered markdown of the latest email + email list of older messages in this subject.
- `/groups/{id}` — group detail view: combined timeline across child subjects, grouped visually by `subject_slug`.
- "+ New group" flow: multi-select subjects, name the group, save to `users/{uid}/groups/{group_id}`. Update `subject.group_id` on each child.
- Folder rename: editing the `display_name` of a subject doesn't change the `subject_slug` — routing stays intact.

**Done when:** User can see processed emails appear in real-time, click into any subject, browse historical emails on that subject, and combine subjects into a named group.

## Phase D — Ask, NotebookLM mode (Week 5–7)

Goal: user can ask grounded questions, scoped or global, with citations or honest refusal.

- Per-subject Ask: `/subjects/{slug}/ask` — Sources panel (left) + scoped chat (right). Banner: *"🔒 Asking {subject} · {n} sources · answers come only from this subject."*
- Per-group Ask: `/groups/{id}/ask` — same UI, scope expanded to the group's `subject_slugs[]`.
- Global Ask: `/ask` — scope chip "All subjects ▾" with dropdown to switch.
- Source uncheck persists per `(uid, scope)` in `users/{uid}/excludedSources`. New email arrivals default to checked unless the user has excluded the sender at the project level.
- Refusal phrasing reflects scope: *"...in this subject" / "...in {group_name}" / "...in your inbox."*
- API: `POST /api/rag/answer` is a thin Next.js route that proxies to the Python orchestrator's `rag_service.answer()` over HTTPS, secured via the user's Firebase ID token.
- Streaming: Server-Sent Events from orchestrator → client renders bot bubble incrementally. Edit-in-place pattern (placeholder → final answer).
- Citation chips inline `[Sender · YYYY-MM-DD]`, click → opens the source `.md` in a side drawer.

**Done when:** User can ask a question scoped to one subject and get a cited answer, ask a question that's out-of-corpus and get the verbatim refusal, and switch scopes via the chip.

## Phase E — Drive integration (Week 6–9, gated by OAuth verification)

Goal: `.md` artifacts live in the user's own Drive folder, mirrored from the watcher.

- Replace placeholder folder picker with the real Drive Picker API.
- `lib/drive.ts` — thin wrapper over the Drive Files API.
- Backend: new `notify_drive.py` adapter writes `.md` files to the user's chosen folder when the watcher produces them. Subject sub-folders auto-created on first write.
- "Open in Drive ↗" links throughout the UI: subject sidebar footer, individual email detail view, settings.
- Group folder mirroring: when subjects are grouped in Shomery, their Drive sub-folders move (or are shortcut-ed) under the group's parent folder.

**Done when:** A processed email appears as a `.md` file in the user's Drive within 60 seconds of receipt. User can open Drive on any device and see the same hierarchy as Shomery.

## Phase F — Settings + notification channels (Week 7–10)

Goal: user can configure inbox, watch list, save location, and notification channels self-serve.

- `/settings` page with 5 sections (per `SCREENS_SPEC.md` §6).
- Email digest channel — `notify_email.py` Python adapter using SES or SendGrid. Frequency: each / daily / weekly.
- Telegram channel — extract `notify_telegram.py` from existing `bridge.py` (refactor `bridge.py` to be a thin Telegram adapter, not a god-file). UI to connect/disconnect.
- KakaoTalk channel — UI ready; backend `notify_kakao.py` ships when business registration completes.
- WhatsApp + SMS — UI ready, Python adapters deferred to post-launch (gated on pricing model decision).

**Done when:** User can manage all configuration self-serve from `/settings`. Email digest is sending. Telegram opt-in works. Other channel UIs are present with honest "Connect" or "Coming soon" stubs.

## Phase G — Polish + PWA (Week 10–11)

Goal: ship-ready quality.

- PWA manifest with icons (192, 512, apple-touch-icon).
- Service worker for offline-cached app shell (network-first for Firestore data).
- Loading states (skeletons), empty states, error boundaries on every route.
- Mobile QA across iOS Safari, Android Chrome — test the install-to-home-screen flow on real devices.
- Accessibility pass: keyboard nav, screen reader labels, AA contrast on Emerald-on-white.
- Performance: Lighthouse ≥ 90 mobile.
- Internal alpha with 2–3 pilot users.

**Done when:** A new user can install Shomery as a PWA, complete onboarding on their phone, and reach a working feed within 2 minutes from first tap. Pilot users prefer it over the existing Telegram-only flow.

## Total estimate

11 weeks of focused work for a single developer with strong AI tools (Cursor, Claude Code). Add ~30% slack for QA, security review, and inevitable surprises. Realistic ship target: **~14 weeks** from kickoff.

If Drive verification slips beyond 8 weeks, Phase E delays by the gap — but Phases A–D, F, G all proceed independently and the product still works without Drive in the worst case (just with the placeholder folder copy).

## Risks

- **Drive OAuth verification fails or stalls beyond 8 weeks.** Mitigate with a placeholder Firestore Storage path; product still works without Drive in worst case.
- **Python orchestrator on Mac Mini becomes RAG bottleneck at scale.** Tailscale or Cloudflare Tunnel for stable endpoint; cache common queries; consider Cloud Run if pilot scale exceeds the Mac.
- **WhatsApp/SMS unit economics surprise.** Gate behind paid tier from day one; cap message volume per user.
- **Mobile PWA quirks on iOS.** Budget extra time in Phase G; test early on real iPhone, not just simulator.
- **Refactor of `bridge.py` to channel-publisher pattern is bigger than estimated.** Keep the existing Telegram path running in parallel until the new one is verified; don't cut over until adapter parity is confirmed.

## What's NOT in this plan (intentionally)

- A native mobile app (PWA covers v1).
- A public REST API (deferred until a paying customer asks).
- Multi-language UI (Korean/English at v1.5, not v1).
- Slack adapter (mentioned in v3 RAG plan but not core to this app's launch).
- Workspace / team accounts (single-tenant per uid is the v1 unit).
- Custom branding for white-label resellers.

These are all real opportunities; none of them are required to ship Shomery v1 to its target SMB market.
