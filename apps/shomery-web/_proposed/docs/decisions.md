# Shomery — Decision Log

Reasoning behind the rules in CLAUDE.md. Read this when you have a judgment call to make and the rule alone doesn't tell you which side to land on.

## Markdown is canonical

PDF was the original artifact. Switched to markdown 2026-04-30 because:

- RAG-native — no PDF parsing or OCR loss in the embedding pipeline.
- ~7× smaller (~2KB vs ~15KB for the same email).
- Renders cleanly in Drive, Obsidian, Notion, GitHub.
- Easy to edit if a user wants to correct a summary.

PDF is rendered on demand for users who want it for archival or sharing.

## Subject groups are virtual

Original design moved emails into group folders. Rejected because:

- The `subject_slug` is the immutable routing key — moving emails would break the contract that new emails on a subject bind to the same folder forever.
- Ungrouping would require re-routing every email.
- The user need is a *view* abstraction, not a data move.

Group is a Pipelane-level record `{group_id, name, subject_slugs[]}`. Adding/removing a subject is a single field update. Emails never move. Ungrouping is risk-free — children pop back out as standalone subjects, no data lost.

A subject can be in zero or one groups (not many). Multi-tag would make the Drive mirror painful and SMB users won't miss it.

## NotebookLM-mode scoping

Per the v3 RAG plan, the bot answers ONLY from the user's own corpus. We extended this to per-subject and per-group scopes because:

- A user asking about "Acme Deal" doesn't want the answer to leak in from an unrelated personal email.
- Smaller scope = tighter retrieval = better answers.
- The Sources panel makes the universe visible — load-bearing for trust. Users uncheck a source and watch the next answer respect that.

Refusal phrasing reflects the scope (*"...in this subject" / "...in {group}" / "...in your inbox"*) because honesty about the bound is the trust contract.

## Telegram is opt-in, not default

Pilot users found Telegram confusing. Installing the app, finding the bot, pasting a `/start` code is a too-tall activation cliff for SMB users — most don't have Telegram and the entire onboarding stalls there.

Email digest became the default because every SMB user already has email. Telegram works fine once installed; it's just not where new users start.

Globally, KakaoTalk for Korea-leaning customers and WhatsApp for everyone else are the natural second channels. SMS is a universal fallback for users who don't want to add another app.

## Brand green is not a status color

Once Emerald became the brand, using green to mean "new" or "success" or "unread" would dilute the brand and force the eye to disambiguate "is this thing important or just branded?" Amber `#F59E0B` is hue-distant from green and reads as "needs attention" without screaming.

Channel-icon colors stay at the third party's actual brand color (WhatsApp `#25D366`, KakaoTalk `#FEE500`, Telegram `#0088CC`). Emerald and WhatsApp green are different hues — one is teal-leaning, one is yellow-leaning — so they stay distinguishable side by side.

## No `firebase-admin` in the web app

Admin SDK runs on the server with elevated privileges. Bundling it into a web app would either leak privileges to the client (catastrophic) or require careful tree-shaking (fragile and bug-prone). Server-side concerns stay server-side. CI greps for `firebase-admin` in `src/` and fails the build if it appears.

## Two-seams architecture

The original email2ppt was designed with state-store and blob-store seams selected by config flag. Shomery's pre-Drive-verification storage at Firebase Storage `summaries/{uid}/{subject_slug}/{email_id}.md` is exactly that seam in action — when Drive clears, swap one helper function and the rest of the app doesn't change. Reads go through one helper specifically so the swap is contained.

## Light mode only in v1

SMB users in B2B contexts strongly prefer light. Dark mode is non-trivial work (every component variant, every contrast pair re-checked) and adds maintenance cost. Defer until a paying customer asks.

## Single Firebase project for portal + Shomery

Considered separate Firebase projects for the legacy portal and the new web app. Rejected because:

- Shared auth — existing tenant_id/uid keeps working across both surfaces.
- Shared Firestore security rules.
- Single billing and monitoring boundary.
- Existing pilot users authenticate once and both apps work.

Cost of unified project: tighter coupling between admin and customer surfaces. Acceptable at SMB scale.

## Hybrid build, not full rewrite

The Python pipeline (watcher, KMS, audit, GDPR cleanup, retention sweeps, Pydantic schemas, CI) represents months of compliance work that changes very little in the new design. Rewriting would lose that infrastructure and restart pilot relationships from zero. The actual gap was UX-shaped, not pipeline-shaped — so the user-facing surface gets greenfield while the pipeline gets additive changes only.
