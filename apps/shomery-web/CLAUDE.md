# Shomery — Customer-Facing Web App

> **Read this file first** when starting any work on the `apps/shomery-web/` codebase. It captures product intent, architecture, brand, and the load-bearing constraints that have already been decided. If something here contradicts older code or comments, this file wins.

---

## What Shomery is

Shomery is a private "NotebookLM for your inbox." It watches a user's Gmail for emails from senders or domains they specify, summarizes each one with a local LLM, saves the summary as a markdown file in the user's own Google Drive folder, and lets the user ask grounded questions about any individual email or about a whole subject's worth of emails. Answers come only from the user's own corpus; the assistant refuses if the answer isn't in there.

The target market is small and medium businesses, Korea-leaning at launch and global afterward. The brand voice is confident, calm, plain-spoken — Apple-clean visual design with a single emerald accent (`#10B981`).

**Naming history:** the product was internally called "Pipelane" as a working placeholder. The brand name is now **Shomery**. If you find any code or comment still saying "Pipelane," update it. Any pre-existing Firestore documents, slugs, or storage paths containing `pipelane` must be renamed via a one-time migration before launch (track as a launch-checklist item). All new writes use `shomery`.

---

## How Shomery fits in the broader project

Shomery is the new customer-facing PWA. It sits inside the existing `email2ppt` monorepo as a sibling to the Python pipeline, sharing the same Firebase project for auth, Firestore data, and security rules.

```
email2ppt/                          (monorepo root)
├── watcher.py                      Python: polls Gmail, summarizes, writes .md
├── digest.py, ppt.py               Python: scheduled digests, on-demand decks
├── bridge.py                       Python: Telegram channel adapter
├── orchestrator.py                 Python: RAG retrieval + grounded synthesis
├── firestore_*.py                  Python: Firestore wrappers (do not bypass)
├── kms_envelope.py                 Python: KMS encryption — DO NOT touch
├── apps/
│   └── shomery-web/                ← THIS APP — new customer PWA
└── shared/types/                   TypeScript types shared with future web packages
```

The Python pipeline is owned by the existing engineering work. Shomery (web) is the new build. **Don't modify the Python pipeline from this folder unless explicitly asked.** If a feature needs a backend change, raise it explicitly so it can be reviewed against the existing security/audit/KMS architecture.

---

## Tech stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript, strict mode
- **Styling:** Tailwind CSS + shadcn/ui (full component code ownership)
- **Auth:** Firebase Auth (Google OAuth)
- **Data:** Firestore client SDK (real-time via `onSnapshot()`)
- **Hosting:** Firebase Hosting
- **State:** React Server Components for server-rendered pages. Firestore `onSnapshot()` is the cache for real-time per-user collections (feed, subjects, channel config). React Query is used **only** for non-Firestore HTTP calls — RAG service, Cloud Functions, OAuth callbacks. Do not wrap Firestore reads in React Query: pick one cache per data source.
- **i18n:** `next-intl` from day one. v1 ships with three locales — **English (default), Korean (`ko`), Portuguese – Brazil (`pt-BR`)**. Locale routing under `/[locale]/...`; user preference persisted in Firestore. All copy goes through translation files; no hardcoded strings in components.
- **Observability:** Sentry for client error tracking (DSN in a public env var, sample rate 100% in v1 since pilot volume is low). No third-party product analytics in v1; if web vitals are needed, use Next.js built-ins.
- **Local dev:** Firebase Emulator Suite (Auth + Firestore + Functions + Storage).

Avoid: Redux, MobX, css-in-js libraries, design-system packages other than shadcn/ui.

---

## Quality gates

These are non-negotiable for v1. Every PR must satisfy all four.

1. **Testing.** Three layers, each owned by a different file pattern:
   - **Unit / component:** Vitest + React Testing Library. Cover every component branch and every non-trivial hook. Coverage gate ≥ 70% lines on `src/**` excluding generated code.
   - **Integration:** runs against the Firebase Emulator Suite. Covers Firestore reads/writes, security rules (positive + negative cases), and Cloud Function invocations. Every new security rule needs a test that *fails* without it.
   - **End-to-end:** Playwright. Minimum smoke flow: sign in → onboarding → feed loads → ask a scoped question → receive grounded answer. Add an E2E for every user-visible regression once it ships.
2. **Accessibility.** WCAG 2.1 AA target. All interactive elements keyboard-reachable, focus state visible, semantic landmarks present, color contrast ≥ 4.5:1 for body text. `eslint-plugin-jsx-a11y` runs in CI; manual VoiceOver/TalkBack pass before each release.
3. **Type safety.** `tsc --noEmit` is a CI gate. No `any`, no `@ts-ignore`, no `// eslint-disable` without a one-line comment naming the reason.
4. **i18n discipline.** No hardcoded user-facing strings in components — every string lives in `messages/{locale}.json`. CI lints for raw JSX text.

---

## Firebase configuration

- **Project:** Use the existing `email2ppt` Firebase project (the one the Python pipeline writes to). Do **not** create a new project.
- **App registration:** Register a new Web app under the existing project; Shomery has its own `firebaseConfig`.
- **Hosting site:** New site `shomery-web` under that project.
- **Domain:** `shomery.web.app` (free) at first; custom domain like `app.shomery.com` once registered.
- **OAuth authorized domains:** Add the Hosting domain to Firebase Auth → Settings → Authorized domains.
- **Security rules:** Existing per-`uid` Firestore rules apply. No new rule scopes for v1. Storage rules added for the v1 markdown seam (see *Critical decisions* #1).

---

## Brand guardrails

| | Value |
|---|---|
| Name | Shomery |
| Mode | Light/bright only — white canvas, no dark surfaces in v1 |
| Accent color | `#10B981` (Emerald — bright green) |
| Accent hover | `#059669` (Emerald 600 — for button hover/active) |
| Ink (text) | `#111111` |
| Soft text | `#6B7280` |
| Paper | `#FFFFFF` |
| Tint (subtle bg) | `#ECFDF5` (Emerald 50 — pale green for callouts and selected rows) |
| High-priority warn | `#F59E0B` (Amber 500 — for "high priority" badges; never green, since green is the brand) |
| Typography | Inter — Regular (400) and Bold (700) only |
| Motif | Accent edge — 3px `#10B981` left border on summaries and hero cards |
| Voice | Confident, calm, plain-spoken |

**Banned words in copy:** synergy, leverage, AI-powered, smart, intelligent, solutions, enterprise-grade, revolutionary, game-changing, cutting-edge, seamless, frictionless, robust, paradigm.

**Approved phrases for describing what Shomery does** (use these instead of the banned ones above): "grounded in your inbox", "answers from your own corpus", "private to you", "your own data, summarized", "watches the senders you choose", "refuses what it can't ground." When you need to refer to the LLM in user-facing copy, say **"the assistant"** or **"the model"** — never "AI." Internal docs and code can use "LLM" freely.

**Light mode is canonical.** White background, dark text. Dark mode is a v2 consideration; do not introduce dark UI surfaces in v1.

**Channel-icon colors stay at the third party's actual brand color** (KakaoTalk `#FEE500`, WhatsApp `#25D366`, Telegram `#0088CC`, etc.) — these are *third-party* brand identities inside Shomery's UI, distinct from Shomery's own accent. Emerald (`#10B981`) is sufficiently different from WhatsApp green (`#25D366`) — one is teal-leaning, one is yellow-leaning — so the eye keeps them apart.

**Green is the brand, not a status color.** Do not use the brand green to indicate "new" / "success" / "unread" — those need a different color so the brand can stay the brand. Use Amber (`#F59E0B`) for high-priority highlights, gray (`#6B7280`) for muted/read state, the brand green only for navigation, primary actions, and the accent edge.

---

## Core screens (v1 scope)

1. **Sign in** — Google OAuth only. One button. No password fields. No alternative paths.
2. **Mobile-style onboarding** — three steps after a Welcome screen: connect Gmail, define watched senders/domains, choose a Drive folder. Each step is its own screen with a 3-dot progress indicator. Big primary "Continue" or "Start watching" button anchored at the bottom.
   - **Current state:** the flow is live and gates `/feed` and `/subjects/*`. A signed-in user without `users/{uid}.onboardingCompletedAt` is redirected to `/[locale]/onboarding`; completing the **Watched senders** step (the only interactive step in v1) writes `priorityWatchSenders`, and "Start watching" sets `onboardingCompletedAt` and routes to `/feed`. The Connect-Gmail and Save-location steps are informational placeholders — Gmail watching is owned by the Python pipeline out-of-band, and the Drive picker is gated on OAuth verification.
3. **Feed** — chronological list of processed emails, rendered inside the persistent app shell (left sidebar + main pane). Each card matches the Telegram bot card layout: mailbox emoji + sender, subject, two-bullet summary, priority badge, timestamp, attached `.md` filename and size. When the item carries a `markdownStoragePath`, a "Read full →" link in the card footer opens the per-item markdown reader at `/[locale]/subjects/[slug]/items/[itemId]`.
4. **Subjects** — left-rail sidebar of the user's folders. Selecting a subject opens a per-folder detail page that lists every item in that folder using the same card the Feed uses. The per-item page renders the item's `.md` with `react-markdown` + GFM via the `getMarkdown(item)` helper, which today reads the v1 Storage seam at `summaries/{uid}/{slug}/{emailId}.md` and is the single switch point for the future Drive backend. The watcher emits `.md` blobs to that path and sets `markdownStoragePath` on the item doc, so newly-processed items render real markdown; items processed before this rollout still show the empty state until they're re-summarized.

   **Ask this subject** is live. From the subject detail header, a primary CTA opens `/[locale]/subjects/[slug]/ask` — a NotebookLM-style split: a `SourcesPanel` (read-only in v1: every item in the folder is rendered as a checked, disabled checkbox so users can see what's being searched; per-item exclusion ships in v2) and an `AskPanel` that posts to the Python `rag_service` at `NEXT_PUBLIC_RAG_BASE_URL` with the user's Firebase ID token. The service runs on the Mac Mini against Ollama and returns a grounded answer (or a refusal when nothing matches). Answers render via `react-markdown` + GFM. Provider is one env var swap on the backend (`LLM_PROVIDER`) when we move off Ollama. **Virtual groups and per-group Ask scoping still ship in dedicated PRs.**
5. **Settings** — five sections: Inbox (Gmail connection), What to watch (sender/domain list), Where to save (Drive folder), Notifications, Privacy & data (export, delete account).
   - **Current state:** the **Watched senders**, **Notifications**, and **Privacy & data** editors are live. Watched senders writes `priorityWatchSenders` on `users/{uid}/config/main`; Notifications writes `digestEnabled`, `telegramEnabled`, and `telegramChatId` on the same doc (rules allow that exact allowlist). Privacy & data: **Export** reads identity + config + folders + items via the client SDK and downloads a JSON file (no Cloud Function needed); **Delete account** calls the `deleteAccount` Cloud Function (admin SDK) which recursive-deletes Firestore under `users/{uid}/**`, deletes Storage prefixes `summaries/{uid}/` and `pdfs/{uid}/`, and finally removes the Auth user. The remaining two sections (Inbox, Where to save) ship in dedicated PRs. The page is reachable from the sidebar's Settings link.
   - **Notifications section, v1 reality:** five channel rows are rendered, but only **Email digest** and **Telegram** are interactive. KakaoTalk, WhatsApp, and SMS render as disabled rows with a *Coming soon* badge — the surface stays the same shape so the v1.x adapters can light up in place without a layout change.

The "Ask" experience is bound to a scope: per-subject, per-group (combined timeline of grouped subjects), or global. Scope is always visually explicit at the top of the chat panel.

---

## Data model (Firestore)

Defined in `shared/types/`. Mirrors what the Python pipeline writes today (`firestore_folders.py`, `firestore_users.py`). The web app imports from there; the compile breaks when the schema drifts.

The pipeline writes a per-folder, per-item shape — not a flat `email_summaries` collection. The web Feed reads items via a collection-group query filtered by `uid`.

```typescript
// users/{uid}/folders/{subjectSlug}
type Folder = {
  subject: string;
  subjectSlug: string;
  folderPath: string;
  pdfCount: number;
  hasSummaryCsv: boolean;
  createdAt: Timestamp;
  updatedAt: Timestamp;
  summaryCsvStoragePath?: string;
};

// users/{uid}/folders/{subjectSlug}/items/{itemId}
type FolderItem = {
  uid: string;                       // denormalized for collection-group query + security rules
  folderSubject: string;
  folderSlug: string;
  date: string;                      // free-form email date header
  from: string;                      // free-form "Name <addr@example.com>"
  urgency: "low" | "med" | "high";
  keyPoints: string[];
  asks: string[];
  suggestedResponse: string;
  pdfFilename: string;
  createdAt: Timestamp;
  pdfStoragePath?: string;
};

// users/{uid} — identity. Web client writes the five fields below on sign-in.
// Python (admin SDK) writes the gmail.* subtree separately; rules forbid the web client from touching it.
type UserIdentity = {
  email: string;
  displayName: string;
  photoURL: string;
  createdAt: Timestamp;
  lastSignedInAt: Timestamp;
};

// users/{uid}/config/main — runtime config consumed by Python.
// Read-only from web today; the future Settings UI will write specific fields.
type UserConfig = {
  priorityWatchSenders: string[];
  watcherLookback: string;
  digestEnabled: boolean;
  userDisplayName: string;
  retentionDays: number;
  summaryPersona: string;
  summaryKeyPointsMax: number;
  summaryAsksMax: number;
  intervalMinutes: number;
};

// users/{uid}/groups/{groupId} — virtual subject groupings, owned by the web app.
// Membership is a flat list of folder slugs. A subject belongs to zero or one groups;
// the invariant is enforced client-side in the useGroups hook (Firestore rules can't express it).
type Group = {
  groupId: string;
  name: string;
  subjectSlugs: string[];
  createdAt: Timestamp;
  updatedAt: Timestamp;
};
```

Deferred to the PRs that introduce them: an explicit `Subject` model (today, "subject" is implemented as a `Folder`; an explicit `Subject` type arrives when the Subjects PR ships), `ChannelConfig` (added when the second notification channel beyond Telegram lands — see *Core screens* §5), markdown artifacts at `summaries/{uid}/{subject_slug}/{email_id}.md` (added when the watcher gains markdown emission — see *Critical decisions* #1).

---

## Critical decisions already made (do not re-litigate)

1. **Markdown is canonical**, not PDF. The watcher renders each email to a `.md` document. PDF is generated on demand via a "Download .pdf" button.
   - **v1 storage seam (pre-Drive-verification):** `.md` content lives in **Firebase Storage** at `summaries/{uid}/{subject_slug}/{email_id}.md`. The Firestore `EmailSummary` document carries `markdown_path` pointing at that object. The web app fetches via the Storage SDK with the user's auth token; Storage rules scope reads to `request.auth.uid == uid`.
   - **Post-Drive-verification swap:** the watcher writes the same `.md` to the user's chosen Drive folder and updates `markdown_path` to a `drive://...` URI. The web read happens through one helper (`getMarkdown(summary)`); swapping the storage backend is a single function change in that helper.
2. **Subject groups are virtual.** Combining subjects does NOT move emails. The group is a parent reference (`group_id` on the subject; `subject_slugs[]` on the group). Ungrouping is risk-free.
3. **Per-subject and per-group Ask are scoped.** RAG retrieval adds `where subject_slug IN (...)` to the vector search filter; the model never sees chunks outside the scope. Refusal phrase becomes *"I don't have anything in this subject about that"* or *"I don't have anything in {group_name} about that."*
4. **Sources panel persists per-subject uncheck state.** New email arrivals default to checked unless the user has explicitly excluded that sender at the project level.
5. **Telegram is opt-in, not the default.** The default notification channel is Email digest. Other channels in priority order: KakaoTalk, WhatsApp, Telegram, SMS.
6. **A subject can be in zero or one groups, not multiple.** No multi-tag in v1.
7. **Drive folder is canonical for saved artifacts** when Drive is connected. Once Drive is verified and connected for a user, Shomery reads metadata from Firestore but the `.md` files themselves live in the user's Drive (see #1 for the v1 seam that precedes this).

---

## Critical things NOT to do

1. **Do not import `firebase-admin` in the web app.** Use the Firebase client SDK only. Server-side admin operations live in Cloud Functions or the Python backend.
2. **Do not bypass `firestore_*.py` wrappers** if you call into the pipeline-written collections from a Cloud Function. They handle KMS encryption, audit logging, and redaction.
3. **Do not write Drive integration code yet.** Google OAuth Drive write verification is a 4–8 week lead-time item outside our control. Build the feed and Ask flow against the Firebase Storage seam (see *Critical decisions* #1); the swap to Drive is one helper function change when verification clears.
4. **Do not make Telegram the default channel** anywhere in the UI. Pilot users find it confusing. It belongs in Settings as opt-in alongside the other phone-alert options.
5. **Do not call any LLM provider directly** for chat or embeddings. All RAG queries go through the Python orchestrator (`rag_service.answer(query, scope_filter)`) via a thin REST/RPC layer. The provider registry is in-house and swappable.
6. **Do not introduce dark UI surfaces.** Brand is Apple-clean white in v1. Dark mode is v2.
7. **Do not skip the Pydantic boundary.** Any input flowing from web → Python services must be validated by Pydantic models on the backend.
8. **Do not store secrets in client-accessible env vars.** Anything `NEXT_PUBLIC_*` is public. API keys for KakaoTalk / WhatsApp / SMS / Twilio go in Cloud Functions secrets, never in the client.
9. **Do not modify `kms_envelope.py`, `log_redaction.py`, `gdpr_local_cleanup.py`, or `retention_sweep.py`.** These are compliance-critical Python modules outside this app.
10. **Do not hardcode user-facing strings.** All copy goes through `messages/{locale}.json`. The CI lint will reject raw JSX text.

---

## What's deferred (v2 / later)

- Drive integration (gated on OAuth verification).
- KakaoTalk, WhatsApp, SMS adapters (engineered one at a time post-launch).
- Multi-tag subject membership (subject in multiple groups).
- Per-folder batch PDF export (manual `.md → .pdf` exists; batch does not).
- Threading-aware combined view (one email per `.md` for now).
- Native mobile apps (PWA add-to-home-screen is the v1 mobile experience).
- Dark mode.
- Additional locales beyond English / Korean / Portuguese (Brazil).
- Slack adapter (the v3 RAG plan mentions it; it inherits NotebookLM mode automatically when added).

---

## External lead-time tasks (start in parallel with web build)

- **Google OAuth Drive write verification** — open this ticket the same week web app development begins. 4–8 week lead time. Possible CASA security assessment depending on scope tier. *(Status as of 2026-04-30: TBD — fill in here once the ticket is filed: ticket ID, filing date, current verification stage.)*
- **KakaoTalk Bot business registration** — 1–2 weeks once Korean 사업자등록증 is in hand. Required for the Kakao channel adapter.
- **shomery.com domain registration and trademark search** — register before any URL is shared publicly. The 4-question name validation lives in `email2ppt/marketing/14_branding_guide.md`.

---

## References

Canonical project decisions live in the assistant's memory at `~/Library/Application Support/Claude/local-agent-mode-sessions/.../memory/`. Key memories relevant to Shomery:

- `project_email2ppt_architecture.md` — the existing Python pipeline
- `project_email2ppt_subject_topics.md` — Project / Subject / Email hierarchy
- `project_email2ppt_subject_groups.md` — virtual group model
- `project_email2ppt_rag_multichannel.md` — channel-agnostic RAG service
- `project_email2ppt_llm_provider_abstraction.md` — model selection contract
- `project_email2ppt_output_format_markdown.md` — markdown canonical format
- `project_email2ppt_markdown_template.md` — `.md` artifact structure
- `project_email2ppt_pilot_telegram_confusion.md` — why Telegram is opt-in
- `project_email2ppt_web_app_decision.md` — hybrid build decision (this app)
- `project_email2ppt_deployment_strategy.md` — two-seams architecture

In-project documents to consult (paths are relative to the monorepo root `/email2ppt/`):

- `RAG_IMPLEMENTATION_PLAN_v3.md` — the NotebookLM-mode contract Shomery's Ask UI implements.
- `email2ppt/docs/SUBJECT_TOPICS_SPEC.md` — the subject_slug routing rules.
- `email2ppt/marketing/14_branding_guide.md` — brand voice and visual system.

---

## When in doubt

When the codebase implies one direction and this file implies another, **this file wins**. When this file is silent on something, ask the product owner before assuming. When a deferred item starts to feel essential, raise it explicitly rather than building it in scope-creep.
