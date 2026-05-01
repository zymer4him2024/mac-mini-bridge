# Shomery — Screens Spec

> **⚠ Superseded by [CLAUDE.md](./CLAUDE.md) and per-PR plans.** This document is the original UX detail for each screen and is still useful as a starting point when planning a new chunk, but specifics have drifted:
> - Routes are shown without the `/[locale]/` prefix. Real routes are `/[locale]/sign-in`, `/[locale]/feed`, `/[locale]/subjects/...`, etc.
> - The auth route is `/sign-in`, not `/login`.
> - Firestore paths (`users/{uid}/emails`, `users/{uid}/excludedSources`, etc.) are illustrative — the canonical schema lives in `shared/types/` and CLAUDE.md ("Data model").
> - "Pipelane Bot" copy → "Shomery Bot."
> - Settings §6.4 reflects the v1 reality from CLAUDE.md ("Core screens" #5): only **Email digest** and **Telegram** are interactive in v1; KakaoTalk, WhatsApp, SMS render as disabled rows with *Coming soon*.
>
> When this file disagrees with CLAUDE.md, CLAUDE.md wins.

Per-screen UX detail. Companion to CLAUDE.md (brand and architecture) and IMPLEMENTATION_PLAN.md (phasing). When in doubt about *what* a screen does, this file. When in doubt about *whether* a screen ships in v1, CLAUDE.md.

## §1 — Sign-in

**Route:** `/login`
**Auth:** None required (this IS the auth screen).

Single centered card on white canvas. Shomery brand mark + wordmark at top.

- H1: *"Read once. Ask anything."*
- Subhead: *"A private notebook for everything in your inbox."*
- Single button: "Continue with Google" — delegates to `signInWithPopup(googleProvider)`.
- Microcopy: *"No card required. 2-minute setup. Your data stays in your Drive."*

**States:**
- OAuth canceled → stay on screen, no toast.
- OAuth error → toast: *"Couldn't sign in — try again."*
- Already signed in → redirect to `/feed` (or `/onboarding/welcome` if onboarding incomplete).

**Component inventory:** `<BrandMark>`, `<GoogleSignInButton>`, `<MicroCopy>`.

---

## §2 — Onboarding (welcome + 3 steps)

**Routes:** `/onboarding/welcome`, `/onboarding/step-1`, `/onboarding/step-2`, `/onboarding/step-3`
**Auth:** Required. Redirects to `/feed` if `users/{uid}/onboarding.complete === true`.

Mobile-first portrait layout (375px reference width). Each step screen has:

- Back arrow (top-left, hidden on welcome)
- 3-dot progress indicator (filled vs empty)
- Step label "STEP N OF 3" (uppercase, small)
- Heading + subheading
- Form area (or single button)
- Primary CTA anchored at bottom (full-width)

**Welcome:** No progress indicator. Brand mark, "Welcome to Shomery," "Read once. Ask anything." subhead, "Get started" button.

**Step 1 — Connect Gmail.** Heading: *"Connect your Gmail."* Subhead: *"We only read what you tell us to. Your data stays in your account."* CTA: "Continue with Google" — delegates to existing email2ppt Gmail OAuth flow.

**Step 2 — What to watch.** Heading: *"What should I watch?"* Subhead: *"Senders or domains. Shomery summarizes anything they send."* Form: chip input (each entry = removable pill). Allow paste of comma-separated list. Empty state: just the input with placeholder *"e.g., @acme.com or maya@acme.com."* CTA: "Continue."

**Step 3 — Where to save.** Heading: *"Where should we save?"* Subhead: *"A Drive folder. One sub-folder per subject, with a markdown file per email."* Form: folder picker. **Pre-OAuth-verification (Phase B–D):** show a static placeholder *"📁 My Drive / Shomery"* with "Change" disabled and a small note *"Drive integration ships soon — your summaries are saved securely in the meantime."* **Post-verification (Phase E):** real Drive Picker API. CTA: "Start watching."

**Done state:** Sets `users/{uid}/onboarding.complete = true` and redirects to `/feed`. The watcher should pick up new tracked senders within the next 5-minute polling cycle.

---

## §3 — Feed

**Route:** `/feed` (default landing for authenticated users post-onboarding)
**Auth:** Required.

**Top bar:** brand wordmark + brand mark + nav (Feed | Subjects | Ask | Settings) + user avatar (round, initials on tinted background).

**Page header:** H2 *"Today"* + subhead *"{n} new emails processed · all saved to Drive."*

**Card list:** chronological `EmailSummary` cards, newest first. Each card:

- Top row: 📄 attachment chip with filename + size (left) + relative timestamp (right)
- Sender row: 📬 + bold sender name
- Subject line (regular weight)
- 2–5 summary bullets
- Priority badge: ▪ LOW (gray) / ▪ MEDIUM (gray) / ▪ HIGH (Amber `#F59E0B`)

Card click → `/subjects/{subject_slug}?email={email_id}` (subject view with the clicked email selected).

**Real-time:** `onSnapshot()` on `users/{uid}/emails` ordered by `received_at desc`, limit 50, with infinite scroll for older.

**States:**
- Loading: 3 skeleton cards.
- Empty (new user, no emails yet): *"We're watching for your first email. Tracked senders are listed in Settings."* with a "Manage tracked senders →" button.
- Error: error boundary card with retry button.

---

## §4 — Subjects (sidebar + detail)

**Routes:** `/subjects` (no slug → "pick a subject" empty state), `/subjects/{slug}`, `/groups/{id}`
**Auth:** Required.

**Layout:** 200px sidebar + flex-1 main pane. Below 768px width, sidebar collapses to a slide-in drawer triggered by a hamburger icon.

### Sidebar

- Section header *"SUBJECTS"* + "+ New group" link (Emerald color).
- Grouped subjects: parent group row with `▼` expander, child subjects indented 1 level.
- Ungrouped subjects: below a thin divider.
- Each row: name (left) + count badge "{total} · {unread}" (unread number in Emerald if > 0).
- Sidebar footer: *"📁 Open in Drive ↗"*

### Combine mode (entered via "+ New group")

- Sidebar pivots to checkbox list. Header changes to *"Select to combine"* + "Cancel" link.
- Bottom action card (Emerald-50 tint background): *"Name this group"* input + "Combine N subjects" primary button.
- Subjects already in a group are disabled with explanation tooltip.

### Main pane — subject selected

- Breadcrumb: *"Subjects /"* + subject name (display_name, editable inline on hover).
- H2: subject name + small unread count.
- Action row: "Read" (default state) + "Ask this subject" (primary, Emerald).
- Below: rendered markdown of the latest email in this subject — frontmatter as property card, summary, extracted table, original blockquote, footer (matches `markdown_template.md`).
- Email list at bottom: chronological older emails in this subject as compact rows (sender + subject snippet + date).

### Main pane — group selected

- Breadcrumb: *"Subjects /"* + group name.
- H2: group name + meta *"{n} subjects · {m} emails · {k} unread."*
- Action row: "Read combined timeline" + "Ask this group" (primary).
- Subject list: each child subject as a row with its own count and last-message date.
- Combined timeline: emails from all child subjects, chronological, visually sub-grouped by `subject_slug`.

---

## §5 — Ask (per-subject, per-group, global)

**Routes:** `/subjects/{slug}/ask`, `/groups/{id}/ask`, `/ask`
**Auth:** Required.

**Layout:** 220px Sources panel (left) + flex-1 chat panel (right). On mobile, Sources panel collapses to a "View sources ({n})" pill at the top of chat that toggles a slide-down panel.

### Sources panel

- Header: *"SOURCES"* (uppercase, small) + count badge "{n} in scope" (Emerald-50 background, Emerald text).
- List of email rows: checkbox + sender (bold) + date · subject snippet.
- Default: all checked. Uncheck persists per `(uid, scope)` in `users/{uid}/excludedSources`.
- New email arrivals: default to checked unless their sender is in the project-level exclude list.
- Footer: *"📁 Open folder in Drive ↗"*

### Chat panel

- Top: scope banner — *"🔒 Asking {scope} · {n} sources · answers come only from this {scope_type}."* Background: Emerald-50, text: Emerald-800.
- Messages container, scrollable, alternating bubbles:
  - User: right-aligned, `var(--color-background-secondary)` background, max-width 72%.
  - Bot: left-aligned, white with 0.5px border, max-width 88%, `line-height: 1.55`.
- Bot answers: prose with inline citation chips `[Sender · YYYY-MM-DD]` (Emerald-50 background, Emerald-800 text). Click → opens the source `.md` in a side drawer.
- Refusal: italic muted gray text — exact phrase per scope:
  - Per-subject: *"I don't have anything in this subject about that."*
  - Per-group: *"I don't have anything in {group_name} about that."*
  - Global: *"I don't have anything in your inbox about that."*
- Input box at bottom: *"Ask anything about {scope}…"* + "Ask" button (Emerald primary).
- Microcopy below input: *"Answers come only from your own emails. Shomery refuses if it isn't in there."*

### API

`POST /api/rag/answer` (Next.js route) → forwards to Python orchestrator's `rag_service.answer()` over HTTPS, secured via Firebase ID token.

Request body:
```json
{
  "question": "What did Acme say about budget?",
  "scope_type": "subject" | "group" | "global",
  "scope_id": "pilot-200-seat" | "acme-deal-grp" | null,
  "excluded_sources": ["email_id_1", "email_id_2"]
}
```

Response: streaming SSE with `{type: "token", token: "..."}` chunks, then `{type: "citations", citations: [...]}`, then `{type: "done", refused: false}` or `{type: "done", refused: true}`.

---

## §6 — Settings

**Route:** `/settings`
**Auth:** Required.

Page background: `#F9FAFB` (slightly off-white, iOS-style). Section cards are white. Each section has a small uppercase label above it.

### §6.1 — Inbox

- Card with one row: *"Gmail"* + email address + green dot + "Connected" + "Disconnect" link.

### §6.2 — What to watch

- Description: *"Senders & domains. Shomery summarizes anything from these."*
- Chip cluster: each entry as a removable pill. "+ Add" inline (Emerald color).

### §6.3 — Where to save

- Row: *"📁 {folder_path}"* + description *"One sub-folder per subject · markdown files · PDF on demand."*
- "Change" button (disabled pre-Drive-verification).

### §6.4 — Notifications

- 5 channel rows in this order:
  1. **Email digest** — small @ icon (Emerald-50 background, Emerald @ symbol). "Default" pill in Emerald. Frequency dropdown: "Each email ▾" / "Daily digest" / "Weekly digest."
  2. **KakaoTalk** — yellow `#FEE500` icon with "K". "Push alerts via Kakao Bot." Connect button.
  3. **WhatsApp** — green `#25D366` icon with "W". "Push alerts via WhatsApp Business." Connect button.
  4. **Telegram** — blue `#0088CC` icon with "T". "Push alerts via Pipelane Bot" (rename to "Shomery Bot" in copy). Connect button.
  5. **SMS / Text message** — neutral icon with "#". "A short text per processed email. Standard rates apply." Connect button.

### §6.5 — Privacy & data

- Row: *"Export your data"* + "Download every saved markdown summary as a zip." + "Export" button.
- Row: *"Delete account"* + "Remove all summaries, embeddings, and your Drive connection." + red "Delete" link → confirmation modal → triggers GDPR cleanup pipeline.

---

## Component inventory (high-level)

Implementations live under `components/`. Most use shadcn/ui primitives wrapped with Shomery-specific styling.

| Component | Used by | Notes |
|---|---|---|
| `<TopBar>` | every authenticated route | Brand + nav + avatar |
| `<BrandMark>` | login, top bar | 14px Emerald square + wordmark |
| `<EmailCard>` | feed, subject view | Matches Telegram bot card layout |
| `<MarkdownRenderer>` | subject detail, drawer | `react-markdown` + `remark-gfm` for tables |
| `<FrontmatterCard>` | subject detail | Renders YAML frontmatter as property card |
| `<SubjectSidebar>` | subjects, groups | Tree view with combine mode |
| `<SourcesPanel>` | all Ask routes | Checkbox list + count badge |
| `<ScopeBanner>` | all Ask routes | "🔒 Asking …" Emerald-50 banner |
| `<ChatBubble>` | Ask | User + bot variants |
| `<CitationChip>` | bot bubbles | Inline link to source `.md` |
| `<ChannelRow>` | settings | Channel icon + name + Connect |
| `<EmptyState>` | feed, subjects, ask | Generic empty pattern |
| `<SkeletonCard>` | loading states | Matches `<EmailCard>` shape |
| `<ProgressDots>` | onboarding | 3-dot progress indicator |
| `<PriorityBadge>` | email card | LOW (gray) / MEDIUM (gray) / HIGH (Amber) |

## Routes summary

| Route | Auth | Phase |
|---|---|---|
| `/login` | none | A |
| `/feed` | required | A (empty), C (real cards) |
| `/onboarding/welcome` | required | B |
| `/onboarding/step-{1,2,3}` | required | B |
| `/subjects` | required | C |
| `/subjects/{slug}` | required | C |
| `/subjects/{slug}/ask` | required | D |
| `/groups/{id}` | required | C |
| `/groups/{id}/ask` | required | D |
| `/ask` | required | D |
| `/settings` | required | F |
| `/api/rag/answer` | bearer token | D |
