# Privacy Notice

This notice describes the personal data email2ppt collects, where it is
stored, how long it is retained, and the rights you have under GDPR and
similar privacy laws.

## What we collect

| Data | Source | Where it lives |
| --- | --- | --- |
| Your Google account email + display name | Firebase Auth (Google sign-in) | Firebase Auth + `users/{uid}` doc |
| Gmail OAuth refresh token | Google OAuth callback | `users/{uid}/secrets/gmail` (server-side only; never sent to browser) |
| Subjects, senders, dates, and bodies of emails matching your priority senders | Gmail API | Worker host disk: `~/email-pdfs/{uid}/`, `~/email-digests/{uid}/` |
| AI-generated summaries of those emails | Local Ollama LLM | Same as above |
| Telegram chat ID, username, first name (if you link Telegram) | Telegram bot | `users/{uid}.telegram` |
| Your Telegram bot token (if you supply your own bot) | Customer-bot setup | `users/{uid}.customerBot.token` (server-side only) |
| Run history (timestamps, status, error messages, file names) | Workers (`watcher`, `digest`, `ppt`, `config_sync`) | `users/{uid}/activity/*` |
| Watcher dedup state (Gmail message IDs only — no content) | `watcher` | `users/{uid}/state/watcher` |

We do not sell or share your personal data with third parties for their own
marketing purposes.

## Sub-processors

email2ppt forwards data to the following sub-processors:

- **Google Cloud / Firebase** — Firestore, Cloud Functions, Firebase Auth,
  Hosting (data residency: multi-region; the Firestore database `email2ppt`
  lives in `nam5`).
- **Google Workspace / Gmail API** — only the messages your priority-sender
  filter matches.
- **Telegram** — message and document delivery to the chat ID you linked.
- **Local Ollama LLM** — runs offline on the worker host. No data is
  transmitted to third parties for summarization.

We do **not** send your email content to any cloud LLM provider (OpenAI,
Anthropic, Google Vertex AI, etc.).

## Retention

| Data | Retention |
| --- | --- |
| Firebase Auth account | Until you delete your account |
| `users/{uid}/secrets/*` | Until you click *Disconnect Gmail* in the portal |
| `users/{uid}/activity/*` | 30 days (auto-deleted via Firestore TTL) |
| `users/{uid}/state/watcher` | Last 200 message IDs (rolling) |
| `telegram_link_tokens/*` | 24 hours (auto-deleted via Firestore TTL) |
| Local PDFs and digests | Indefinite today; per-user retention sweep planned for Phase B (default 30 days) |
| Worker logs (`*.log`, `*.std{out,err}.log`) | Indefinite today; rotation planned for Phase B (10 MB / 7 generations) |

## Your rights (GDPR, CCPA, and similar)

You can:

- **Access** — download the data we hold about you (planned Phase B; today,
  request via `privacy@email2ppt.example`).
- **Correct** — update your priority-senders list in the portal.
- **Delete** — disconnect Gmail in the portal; this revokes the OAuth
  token and removes `users/{uid}/secrets/*` and `users/{uid}.gmail`. A
  comprehensive *delete-my-account* flow that also purges activity, state,
  and local files is planned for Phase B.
- **Object / restrict** — pause the watcher and digest by toggling
  `digestEnabled` and clearing your priority-senders list.
- **Portability** — request an export of your data (Phase B).

To exercise any of these, email `privacy@email2ppt.example`.

## Lawful basis

Where GDPR applies, our lawful basis for processing is **consent** (you
opt in by signing in and granting Gmail OAuth scope) and **legitimate
interest** (delivering the service you have asked for). You can withdraw
consent at any time by disconnecting Gmail.

## Children

email2ppt is not directed to children under 16. We do not knowingly
collect data from children.

## Changes

This notice will be updated when our data practices change. The portal
will surface a banner when material changes are made.

## Contact

`privacy@email2ppt.example` for any privacy or data-rights request.
