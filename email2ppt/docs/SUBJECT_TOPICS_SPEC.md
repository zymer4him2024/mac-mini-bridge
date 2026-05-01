# Subject-Scoped Telegram Forum Topics — Technical Spec

**Status:** Draft
**Author:** Shawn Lee
**Decided:** 2026-04-29
**Audience:** Self + AI coding agents (Cursor, Claude Code) implementing this change

---

## 1. Overview

We replace the existing flat "one Telegram chat per user" routing model with a three-level **Project → Subject → Email** hierarchy that maps directly onto Telegram's Forum Topics feature. Each user organizes senders into named projects (e.g., *Acme Acquisition*, *2026 Summer Launch*, default *Inbox*); each project links to its own Telegram forum group; within a project, every email subject becomes a Forum topic via auto-create rules (priority sender or threshold reached) plus manual Pin/Archive/Promote controls. The backend remains a single Telegram bot — bot identity is not the abstraction boundary, the project is. Phase 1 ships the backend infrastructure with backwards-compatible defaults so existing single-chat users see no behavior change until they opt in. Phase 2 adds portal UX. Message-ID threading (Phase 3) and folder-scoped RAG (Phase 4) are deliberately out of scope and have separate specs. Decision date: 2026-04-29.

## 2. Goals & Non-goals

### Goals

- **Per-project context isolation.** Each business context (a deal, a launch, a customer) lives in its own Telegram forum group; topic lists never mix unrelated subjects.
- **Subject-level threading inside a project.** Each email subject within a project becomes (or accumulates into) one Forum topic — the natural conversational unit.
- **Smart auto-create that avoids topic explosion.** Topics are created only when a sender is in `priorityWatchSenders` (1st email) or when the threshold is crossed (default: 2nd email of same `subject_slug`). Other one-off emails stay in the project's General topic.
- **Manual user control.** Users can Pin a subject upfront, Archive a noisy one, or Promote one out of General — all from the portal.
- **Backwards compatibility.** Existing users with `users/{uid}.telegram.chatId` continue to receive alerts at that chat with zero behavior change until they create a project and link a forum group.
- **RAG-ready data shape.** The `users/{uid}/projects/{project_id}/folders/{subject_slug}` path provides natural attachment points for future vector indexes — Phase 4 needs no schema migration on this layer.

### Non-goals (explicit, to prevent scope creep)

- **Folder-scoped RAG implementation.** Deferred to Phase 4 with its own spec.
- **Message-ID / References / In-Reply-To threading.** Phase 3, and conditional on observed collision data — not committed.
- **Auto sender-to-project assignment by domain.** Phase 1 is manual-only via portal. Privacy and clarity beat convenience here.
- **Multiple Telegram accounts per uid.** A given uid binds to one Telegram identity; multi-account support is a separate Phase 5+ design.
- **Cross-project topic merge UX.** Phase 1 and 2 provide no in-product way to move topics between projects; manual Firestore intervention if needed.
- **Hard delete of projects, folders, or topics.** Archive only. Deletion (with retention policies) is a separate future design.
- **Per-tenant custom bot identities beyond existing `customerBot` field.** The current customer-bot fallback is preserved; new identity types are not introduced here.
- **Replacing the existing `_subject_slug` logic.** Slug generation is unchanged except for an **empty-slug fallback** for CJK / non-ASCII subjects (returns `subj-{sha1[:8]}` instead of `"no-subject"`). See Q1 resolution.

## 3. Current State

The email2ppt codebase at `/Users/shawnshlee/1_Claude_Code/email2ppt/` is a **mature multi-tenant Python pipeline**, not a greenfield repo. AI agents implementing this spec should treat the components below as existing and stable — do not reinvent them.

**Subject is already a first-class grouping key**, which is why this spec is mostly additive:

- `watcher.py:_subject_slug()` (lines 361–367) computes URL-safe slugs after stripping `Re:`, `Fwd:`, `Fw:` prefixes and lowercasing. Output is reused throughout the system.
- `~/email-pdfs/{uid}/{subject-slug}/` is the on-disk PDF folder per subject. Filename convention: `{timestamp}_{sender_slug}.pdf` plus a JSON sidecar with from/urgency/key_points/asks. A `_summary.csv` is auto-generated when a folder accumulates ≥5 PDFs.
- `users/{uid}/folders/{subject_slug}` is the Firestore mirror, accessed via `firestore_folders.py`. Fields today: `subject`, `pdfCount`, `hasSummaryCsv`, plus per-PDF item docs at `.../folders/{subject_slug}/items/{id}`.
- `users/{uid}/leads/{lead_id}` deduplicates leads by `lead_id = SHA1(sender_email|subject_slug)`, accessed via `firestore_leads.py`. This spec changes the key to include `project_id`.

**Routing today** (what this spec replaces):

- `firestore_alerts.py:_user_creds(uid)` (lines 40–85) returns `(token, chatId)`. Two delivery paths: the customer's own bot (`users/{uid}.customerBot.token` + encrypted chatId) or the shared bot fallback (`users/{uid}.telegram.chatId` + `TELEGRAM_BOT_TOKEN` env var).
- `bridge.py` (lines 26–34) hosts the python-telegram-bot handlers for incoming messages, including the `/link` command.
- Telegram link flow goes through `firestore_telegram.py` and the `telegram_link_tokens/{tokenId}` top-level collection. Currently captures `chatId` only — no group/topic awareness.
- No subject/thread awareness in alert dispatch today: alerts go to a single chatId per user regardless of which email subject triggered them.

**Other existing components** the spec reuses without modification:

- `users/{uid}/config/main.priorityWatchSenders` — flat list of sender emails for elevated treatment. Loaded by `firestore_users.load_user_config()` (line 111).
- `firestore_activity.py` — append-only audit log at `users/{uid}/activity/{id}`. New event types from §5.1.7 add to this collection without schema change.
- `firestore_state.py` — watcher state (`processedIds`, `lastRunAt`). Unchanged.
- `config_sync.py` — syncs `priorityWatchSenders` to a local `priority_senders.txt` every 5 min. Unchanged.

**Firestore wrapper convention** (per existing code-review feedback): all pipeline code accesses Firestore through `firestore_*.py` wrappers, **never the SDK directly**. New `firestore_projects.py` follows the same pattern.

**Threading is NOT implemented today.** Message-ID, References, and In-Reply-To headers are never extracted or stored. Reply detection is purely regex-based on the subject prefix. Phase 1 of this spec preserves that behavior; Phase 3 may revisit.

## 4. Architecture

### 4.1 Three-Level Hierarchy (Project → Subject → Email)

The system organizes incoming email into a **three-level hierarchy** that maps cleanly onto Telegram's group/topic model:

```
                                Telegram                    Email
                              ────────────              ─────────────
   uid                         (the user)                (the inbox)
    │
    ├── Project A              Forum group A          (cluster of senders)
    │     │
    │     ├── Subject 1        Forum topic 1          (subject_slug)
    │     │     └── emails     messages                (individual emails)
    │     ├── Subject 2        Forum topic 2
    │     └── Subject 3        Forum topic 3
    │
    ├── Project B              Forum group B
    │     ├── Subject 4        Forum topic 4
    │     └── Subject 5        Forum topic 5
    │
    └── Inbox (default)        Forum group "Inbox"    (catch-all)
          └── ...
```

A **Project** is a named cluster of email senders that share a Telegram Forum group. Each user (`uid`) has one or more projects. Projects map 1:1 to forum groups.

Why this layer exists:
- Avoids context collision in the topic list (Acme due-diligence emails don't mix with personal mailing lists).
- Matches the CEO mental model: "I'm running Project X with these stakeholders."
- Privacy boundary: when screensharing one project's forum group, others remain hidden in different forum groups.
- Per-project notification settings become possible (deferred to Phase 2).

**One bot, many forum groups.** The same Telegram bot is added to every project's forum group. The bot identity is *not* the abstraction boundary — the project is. Telegram bots natively support membership in many groups, so this is well-supported by the platform.

**Customer-bot users**: the existing `users/{uid}.customerBot.token` fallback is preserved. For these users, the customer's bot must be added as a member to **every** forum group they link. The portal's link instructions template the bot's `@username` based on the user's resolved bot identity, so the user always sees the right "@bot" to add. There is no automatic check that the bot is in all of a user's forum groups — if the user creates a forum group and forgets to add the bot, `/link` simply won't deliver to that group, and the consume-link-token step will see no command. (The portal can recover by re-issuing a token.)

**Default project: Inbox.** Every user gets an Inbox project auto-created at first watcher run. It's marked `isDefault: true`. Senders not explicitly assigned to any project route to Inbox. This guarantees no email is ever dropped — every sender always has a destination.

**Sender assignment is manual** (per 2026-04-29 decision). Users explicitly assign sender emails to projects via the portal. New unmatched senders land in Inbox; users can promote them into specific projects later. No auto-detection by domain in Phase 1 — privacy and clarity over convenience.

### 4.2 Forum Topics Model (within a Project)

Within a single project's forum group, subjects become topics. The model is identical to a one-group-per-user design, just scoped to one project.

Message flow:

```
Email arrives (Gmail watcher, existing)
    │
    ▼
watcher.py:_subject_slug() computes slug (existing)
    │
    ▼
firestore_alerts.send_alert(uid, text, subject_slug=X, sender_email=Y)
    │
    ▼
_user_creds(uid, sender_email=Y, subject_slug=X) resolves:
    Step 1: sender_email → project_id (project membership lookup)
    Step 2: project_id → forum_chat_id (project's linked forum group)
    Step 3: subject_slug → topic_id within that project's folders
    → returns (bot_token, forum_chat_id, topic_id | None)
    │
    ▼
Bot posts to (chat_id=forum_chat_id, message_thread_id=topic_id)
    └─ topic_id=None → posts to that project's General topic
```

Key invariants:
- One `Project` = one `forum_chat_id`.
- One `uid` may have many projects; one project belongs to exactly one `uid`.
- Subject collisions are **scoped per project**. Two projects can both have a topic named "Q3 Plan" without conflict — they live in different forum groups.
- Each project has its own General topic (Telegram-provided default in every Forum group).
- Telegram is the source of truth for `topic_id`; Firestore mirrors it on `projects/{project_id}/folders/{subject_slug}.topicId`.
- `subject_slug` generation is unchanged — same `watcher.py:_subject_slug()` logic. Forum Topic names use a **cleaned subject** (prefixes stripped, casing preserved, max 80 chars), not the slug.

### 4.3 Topic Lifecycle (State Machine)

The state machine is **per-project, per-subject**. Each `(project_id, subject_slug)` pair is in exactly one of four states. State lives on `users/{uid}/projects/{project_id}/folders/{subject_slug}.topicState`.

```
                  ┌─────────────────────────────────────┐
                  │                                     │
    [new email]   ▼          [user pins]                │
        ┌─────────────┐  ────────────────────►  ┌──────────────┐
   ───► │   General   │                         │   Pinned     │
        │ (no topic)  │  ◄──────[archive]──────┤  (manual)    │
        └─────────────┘                         └──────────────┘
              │                                       ▲
              │ [threshold met OR                     │ [user
              │  priority sender]                     │  elevates]
              ▼                                       │
        ┌─────────────┐                               │
        │ Auto-Active │ ──────────────────────────────┘
        │  (auto)     │
        └─────────────┘
              │
              │ [user archives]
              ▼
        ┌─────────────┐
        │  Archived   │  ──── stays archived; new emails of this subject
        │  (closed)   │       route to General until user manually reactivates
        └─────────────┘
```

State definitions:

| State | Firestore `topicState` | Telegram representation | Meaning |
|---|---|---|---|
| **General** | `null` (folder may not even exist yet) | None — uses the group's default General topic | No dedicated topic yet; possibly accumulating toward threshold |
| **Pinned** | `"pinned"` | Forum topic + a pinned anchor message inside it (`pinChatMessage`) | Manually elevated by user; permanent unless user changes it. *See note below on Telegram-side pinning.* |
| **Auto-Active** | `"auto"` | Forum topic, normal | Auto-created after trigger fired |
| **Archived** | `"archived"` | Forum topic with `is_closed: true` (via `closeForumTopic`) | User explicitly archived; new email routes to General |

**Note on "Pinned" semantics**: Telegram's Bot API does **not** expose a topic-level `is_pinned` flag — `editForumTopic` only updates name/icon. To make a Pinned topic visually distinct, the bot posts a sentinel anchor message inside the topic on creation and pins that message via `pinChatMessage` (with `message_thread_id`). The portal also displays Pinned topics at the top of each project's topic list. So "Pinned" is primarily a Firestore state with two visual reinforcements (anchor pin + portal sort order); it is **not** a Telegram-native topic-pinning feature.

**Triggers for the General → Auto-Active transition** (within a project):
1. Sender's email is in the user's `priorityWatchSenders` config — topic auto-created on the *first* email of this subject within the resolved project. The priority trigger does **not** additionally require the sender to be listed in the project's `senderEmails` array; it's a user-level signal that overrides the threshold regardless of project assignment. (Earlier drafts of this spec had an "AND sender belongs to this project" clause — removed for consistency with §4.4 pseudocode and to make the Inbox catch-all behave as expected.) OR
2. Cumulative email count for `(project_id, subject_slug)` reaches `topicAutoCreateThreshold` (config, default `2`) — topic created on the threshold-crossing email.

The threshold counter is **per-project-scoped**: if the same `subject_slug` appears under Project A and Project B, each has its own independent `emailCount`.

A priority sender whose email isn't in any project's `senderEmails` array routes to Inbox (per §4.4 step 1) and gets a 1st-email auto-create there.

**Topic display name**: Cleaned subject (Re:/Fwd:/Fw: stripped, original casing preserved, truncated to 80 chars per Telegram limit). User can rename via Telegram UI or via the portal at any time; rename is captured back into Firestore for display only — internal routing always uses `subject_slug`.

**Why historical messages don't move on Promote**: The Telegram Bot API does not support moving messages between topics. When a subject is promoted from General to its own topic within a project, only future messages route to the new topic. As a UX courtesy, the bot posts a one-time pointer in the new topic: *"Earlier messages on this subject are in the [General topic](link)."*

**Archive does not delete history**: Archived topics are closed (`is_closed: true`), not deleted. Past messages remain readable. New emails of an archived subject route to that project's General topic until the user explicitly reactivates via the portal.

### 4.4 Routing Rules

Routing happens in three resolution steps: sender → project, project → forum group, subject → topic.

> **Note on this pseudocode**: the function below is **illustrative**, showing the routing decision logic. The real, canonical signature lives in §6.2 as `_user_creds()` returning an `AlertDestination` dataclass. The 2-tuple return shape here is a simplification to keep the routing logic readable; in the actual implementation, the tuple values are wrapped into `AlertDestination` along with the bot token. The sentinel `_LEGACY_FALLBACK` below stands in for the case "fall back to legacy single-chat routing" — concretely, this means returning an `AlertDestination` with `is_legacy=True` and `chat_id=users/{uid}.telegram.chatId`. If that legacy chat ID is also unset, the destination is set to a `Pending Link` queue entry (an activity event of type `alert_pending_link`, with the message text recorded for redelivery once a link completes).

```python
def resolve_routing(
    uid: str,
    sender_email: str,
    subject_slug: str,
    cleaned_subject: str,
) -> tuple[int | None, int | None]:
    """
    Returns (forum_chat_id | None, topic_id | None).
    forum_chat_id=None means: no project linked yet — caller falls back to legacy single-chat.
    topic_id=None means: route to that project's General topic.
    Side effects: may create a Forum Topic via Telegram API and persist topicId.
    Idempotent on retry.
    """

    # Step 1: resolve sender → project (highest-priority match wins; falls back to default Inbox)
    project = firestore_projects.find_for_sender(uid, sender_email)
    if project is None:
        project = firestore_projects.get_default(uid)  # the Inbox project

    # Step 2: project must have a linked forum group
    if not project.forumChatId or not project.isForumEnabled:
        return (_LEGACY_FALLBACK, None)  # caller routes to legacy users/{uid}.telegram.chatId

    # Step 3: resolve subject → topic within this project
    folder = firestore_folders.get(uid, project.id, subject_slug)

    # Case A: existing topic, active or pinned → reuse
    if folder and folder.topicId and folder.topicState in ("pinned", "auto"):
        return (project.forumChatId, folder.topicId)

    # Case B: archived → route to project's General topic
    if folder and folder.topicState == "archived":
        return (project.forumChatId, None)

    # Case C: no active topic; evaluate auto-create triggers
    user_config = firestore_users.load_user_config(uid)
    is_priority_sender = sender_email in user_config.priorityWatchSenders
    new_count = (folder.emailCount if folder else 0) + 1
    threshold = user_config.topicAutoCreateThreshold  # default 2

    should_create = is_priority_sender or new_count >= threshold

    if should_create:
        topic_id = telegram_topics.create_topic(
            chat_id=project.forumChatId,
            name=cleaned_subject[:80],
        )
        firestore_folders.upsert(
            uid, project.id, subject_slug,
            topicId=topic_id,
            topicState="auto",
            emailCount=new_count,
            topicCreatedAt=now(),
        )
        return (project.forumChatId, topic_id)

    # Case D: below threshold, not priority — bump counter, route to General
    firestore_folders.upsert(
        uid, project.id, subject_slug,
        topicId=None,
        topicState=None,
        emailCount=new_count,
    )
    return (project.forumChatId, None)
```

**Failure modes** (full handling in §6.6):

| Scenario | Behavior |
|---|---|
| `createForumTopic` returns rate-limit error | Log, fall back to that project's General topic, retry topic creation on the *next* email of same subject |
| Bot removed from a project's forum group / group deleted | Alerts to that project fail; record in `firestore_activity`; user notified via legacy email-fallback channel; project flagged `isForumEnabled=false` |
| Project's `forumChatId` unset (not yet linked) | Alerts route to legacy `users/{uid}.telegram.chatId` if present; otherwise queued with status `Pending Link` |
| Telegram returns "topic_id no longer exists" (user manually deleted topic) | Clear `folders/{subject_slug}.topicId`, set `topicState="archived"`, route current message to project's General, surface in portal |
| Sender belongs to multiple projects | Highest `priority` wins; tiebreak by `createdAt` ascending |
| Sender belongs to no project | Routes to default Inbox project |

**Routing is idempotent**: the function reads Firestore before any Telegram API call, so re-delivery of the same email does not produce duplicate topics.

## 5. Data Model

### 5.1 Firestore Schema Changes

Three kinds of change: (a) **one new collection** (`projects`), (b) **one moved collection** (`folders` is now nested under `projects`), (c) **additive fields** on several existing collections. No fields are renamed or repurposed. Existing data migrates lazily into a default Inbox project.

#### 5.1.1 NEW collection: `users/{uid}/projects/{project_id}`

A project is a named cluster of senders that maps 1:1 to a Telegram Forum group.

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | `string` | — | Display name (e.g., "Acme Acquisition", "Inbox"). User-editable. |
| `slug` | `string` | — | URL-safe identifier (e.g., "acme-acquisition"). Used for portal URLs and as a stable reference. Auto-generated from name. |
| `senderEmails` | `array<string>` | `[]` | Email addresses assigned to this project. Lowercase, normalized. |
| `forumChatId` | `number \| null` | `null` | Telegram chat ID of the linked forum group. Negative for supergroups (e.g., `-1001234567890`). `null` until user runs `/link` in a forum group targeted at this project. |
| `isForumEnabled` | `boolean` | `false` | True only after `/link` confirms the group is Forum-enabled. |
| `forumGroupTitle` | `string \| null` | `null` | Telegram group title at link time. Display/audit only, not used in routing. |
| `linkedAt` | `Timestamp \| null` | `null` | When `/link` was consumed for this project. |
| `linkedByTelegramUserId` | `number \| null` | `null` | Telegram user_id of who ran `/link`. Audit trail. |
| `isDefault` | `boolean` | `false` | True for the Inbox project. Exactly one project per uid has `isDefault: true`. Catches unmatched senders. |
| `priority` | `number` | `0` | Tiebreak when a sender is in multiple projects. Higher = matched first. Inbox is `0` (lowest). |
| `archived` | `boolean` | `false` | When true, project hidden from portal; senders re-route to Inbox; existing folders/topics remain readable. |
| `createdAt` | `Timestamp` | — | Project creation time. |

**`project_id` doc ID**: ULID or auto-generated short ID (e.g., `proj_abc123`). Stable; never changes even when `name` or `slug` are edited.

**Constraints (enforced in `firestore_projects.py` wrapper):**
- Exactly one project per uid has `isDefault: true`. Wrapper rejects creating a second default and rejects archiving the only default.
- A given `senderEmail` may appear in multiple projects' `senderEmails` arrays — `priority` resolves the routing.
- `slug` must be unique within a uid's projects.

#### 5.1.2 `users/{uid}` — root doc

Add one field; the previously-planned `forumGroup` map field on the user root is **removed from this spec** — that data now lives on individual project documents.

| Field | Type | Default | Notes |
|---|---|---|---|
| `defaultProjectId` | `string \| null` | `null` | Doc ID of the user's Inbox project. Set when Inbox is auto-created at first watcher run after deploy. |

#### 5.1.3 MOVED: `users/{uid}/projects/{project_id}/folders/{subject_slug}`

Folders move from `users/{uid}/folders/` to **nested under projects**. Existing folders migrate lazily into the Inbox project (see §5.2 and §7.3).

Folder document fields (existing pre-spec fields plus new topic fields):

| Field | Type | Default | Notes |
|---|---|---|---|
| `subject` | `string` | — | Original cleaned subject. (Existing field) |
| `pdfCount` | `number` | `0` | (Existing field) |
| `hasSummaryCsv` | `boolean` | `false` | (Existing field) |
| `topicId` | `number \| null` | `null` | Telegram `message_thread_id`. `null` = General topic. |
| `topicState` | `string \| null` | `null` | Enum: `"pinned"`, `"auto"`, `"archived"`, or `null` (General). Validated in wrapper. |
| `topicCreatedAt` | `Timestamp \| null` | `null` | Set when `createForumTopic` succeeded. |
| `topicNameOverride` | `string \| null` | `null` | User-edited topic display name. Routing always uses `subject_slug`, never this. |
| `emailCount` | `number` | `0` | Per-project per-subject counter for auto-create threshold. |
| `senderFingerprint` | `string \| null` | `null` | *(Phase 3a)* SHA1 of the email domain of the first sender to arrive under this folder. Used by the collision guardrail to detect when a different sender domain starts using the same subject_slug. Stays `null` until Phase 3a ships. |
| `collisionWarnings` | `number` | `0` | *(Phase 3a)* Counter incremented each time an incoming email's sender domain doesn't match `senderFingerprint`. Surfaces a "⚠ Possible collision" badge in the portal. Stays `0` until Phase 3a ships. |

**Subject collisions become impossible across projects**: two projects may both have a folder with `subject_slug="q3-plan"` — they live at different paths. The Phase 3 collision concern (different senders sharing the same subject) is now confined to within a single project.

#### 5.1.4 `users/{uid}/leads/{lead_id}` — lead docs

Add two denormalized fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `projectId` | `string \| null` | `null` | Doc ID of the project this lead belongs to. Denormalized for portal queries. |
| `topicId` | `number \| null` | `null` | Telegram `message_thread_id`. Denormalized from the parent folder. Updated on folder topic changes (see §6.3). |
| `subject_slug` | `string` | — | The slug used for grouping. **Already present on existing pre-spec lead docs** (computed from the email's subject at lead-create time). Listed here explicitly because §6.4 `propagate_topic_change` queries leads by `(projectId, subject_slug)` — the field must be a queryable Firestore field, not derived from the lead_id hash. If a contractor finds it missing on legacy leads, run a one-time backfill from the parent folder's slug. |

**`lead_id` keying changes**: existing logic uses `SHA1(sender_email|subject_slug)`. New keying: `SHA1(project_id|sender_email|subject_slug)`. Two senders with the same subject in different projects now produce different lead docs (correct behavior). Migration: existing leads recompute their key on first access via a backfill script (idempotent, safe to re-run).

#### 5.1.5 `users/{uid}/config/main` — user config

Three new fields, identical to previous draft (no project-related changes here):

| Field | Type | Default | Notes |
|---|---|---|---|
| `topicAutoCreate` | `boolean` | `true` | Global kill switch. When `false`, no auto-create across any project; only manual Pin works. |
| `topicAutoCreateThreshold` | `number` | `2` | Email count at which an `Auto-Active` topic is created for a non-priority subject. Min `1`. |
| `topicArchiveBehavior` | `string` | `"route_to_general"` | Reserved for future. Currently only `"route_to_general"` is honored. |

**`priorityWatchSenders` semantics**: still a flat user-level list. The priority flag triggers auto-create within whatever project the sender belongs to (per §4.4). It does **not** override project membership — a priority sender in Project A still routes to Project A's forum group, just creates a topic faster.

#### 5.1.6 `telegram_link_tokens/{tokenId}` — link token docs

Updated link-token model. The token now carries a target project so link consumption knows which project to bind to:

| Field | Type | Default | Notes |
|---|---|---|---|
| `linkTargetProjectId` | `string` | — | Required at token creation. The project this `/link` is intended to bind to. |
| `forumChatId` | `number \| null` | `null` | Set during `/link` consumption from Telegram update payload. |
| `isForumLink` | `boolean` | `false` | True if the consumer was a Forum-enabled group; false for legacy single-chat link. |
| `forumGroupTitle` | `string \| null` | `null` | Telegram group title at link time. |

Existing fields (`uid`, `shortCode`, `createdAt`, `expiresAt`, `consumedAt`, `consumedByChatId`) preserved.

#### 5.1.7 `users/{uid}/activity/{id}` — activity log (new event types)

Existing collection schema unchanged; new `eventType` values added:

- `project_created` — payload: `{projectId, name, isDefault}`
- `project_archived` — payload: `{projectId}`
- `project_linked` — payload: `{projectId, forumChatId, forumGroupTitle}`
- `sender_assigned_to_project` — payload: `{projectId, senderEmail}`
- `sender_removed_from_project` — payload: `{projectId, senderEmail}`
- `topic_created` — payload: `{projectId, subject_slug, topicId, trigger: "priority" | "threshold" | "manual_pin"}`
- `topic_archived` — payload: `{projectId, subject_slug, topicId, archivedBy: "user" | "system"}`
- `topic_pinned` — payload: `{projectId, subject_slug, topicId}`
- `topic_promoted` — payload: `{projectId, subject_slug, fromState, toState}`
- `topic_renamed` — payload: `{projectId, subject_slug, topicId, oldName, newName}`
- `topic_possible_collision` — payload: `{projectId, subject_slug, originalDomain, newDomain, senderEmail}` *(Phase 3a)*
- `alert_pending_link` — payload: `{projectId, subject_slug, sender_email, message_text}` *(emitted when no project is linked yet AND legacy chatId is unset)*
- `alert_failed` — payload: `{projectId, subject_slug, sender_email, error_summary}` *(all delivery attempts failed)*

All topic events now include `projectId` for cross-project audit/debugging.

### 5.2 Backwards Compatibility & Lazy Migration

**Existing users with `telegram.chatId` only**: continue to work on first deploy. `_user_creds()` falls back to legacy `(token, chatId, None)` when no projects are linked. The user is prompted via portal to create their first project — or the system auto-creates Inbox at first watcher run.

**Auto-create the Inbox project**: at the first watcher run after deploy (or first portal load), if `users/{uid}/projects/` is empty, the system creates an Inbox project:
- `name: "Inbox"`, `slug: "inbox"`, `isDefault: true`, `priority: 0`
- `forumChatId: null` (until user links a forum group)
- `senderEmails: []` (catch-all logic uses `isDefault`, not the array)
- The user's `defaultProjectId` is set to this project's doc ID.

**Existing folders under `users/{uid}/folders/`**: migrated **under whichever project_id the caller requests at first access** (see §6.3 `get()` lazy migration). Concretely: if the sender of the first post-deploy email has been assigned to project Acme, the legacy folder migrates under Acme. If the sender hasn't been assigned anywhere, routing falls into Inbox and the folder migrates there. The nightly batch (§7.3) sweeps any folder that wasn't touched lazily and moves it under `default_project_id` as a safety net. Historical `emailCount` is **not** backfilled — only post-deploy emails count toward the threshold (intentional, prevents day-one topic explosion).

**Existing leads**: lead IDs change because keying becomes `SHA1(project_id|sender_email|subject_slug)`. New leads use the new key; existing leads remain at the old key but are returned by the wrapper alongside new ones until the backfill script consolidates them. Backfill is idempotent and can run during off-hours.

**Forward compatibility note**: Phase 4 (Folder-scoped RAG) will likely add a `vectorIndexId` field on `projects/{project_id}/folders/{subject_slug}`. The project nesting actually helps RAG: vector indexes can be project-scoped (cross-subject within a project) or subject-scoped (within a folder), depending on user preference.

**Default-value reads**: All wrappers (`firestore_projects.py`, `firestore_folders.py`, `firestore_users.py`, etc.) must defensively handle missing fields with the defaults in §5.1.* — never raise on docs that pre-date this schema.

All Firestore access continues to go through `firestore_*.py` wrappers — **never call the Firestore SDK directly from pipeline code** (existing convention). Telegram API access for Forum Topics goes through a new `telegram_topics.py` wrapper, keeping `bridge.py` (python-telegram-bot handlers) focused on incoming-message handling.

### 6.1 NEW file: `firestore_projects.py`

Wrapper for the new `users/{uid}/projects/{project_id}` collection. Handles project CRUD, sender-membership management, and forum-group linkage. All wrappers in this codebase return plain dicts; we follow that convention.

```python
# Public API

def create_project(
    uid: str,
    name: str,
    slug: str | None = None,        # auto-generated from name if None
    is_default: bool = False,
    priority: int = 0,
) -> str:
    """Returns the new project_id. Enforces: at most one is_default per uid, unique slug per uid."""

def get_project(uid: str, project_id: str) -> dict | None:
    """Returns project dict or None. Defensive on missing fields per §5.2."""

def list_projects(uid: str, include_archived: bool = False) -> list[dict]:
    """Returns all projects for uid, sorted by priority desc then createdAt asc."""

def update_project(uid: str, project_id: str, **fields) -> None:
    """Partial update. Validates is_default uniqueness, slug uniqueness, priority bounds."""

def archive_project(uid: str, project_id: str) -> None:
    """Soft-delete: sets archived=true. Rejects archiving the only is_default project."""

def find_for_sender(uid: str, sender_email: str) -> dict | None:
    """
    Returns the highest-priority non-archived project containing sender_email
    in its senderEmails array.

    Filter order:
      1. Exclude archived=true projects
      2. Filter projects where sender_email (lowercased) is in senderEmails
      3. Sort by priority desc → createdAt asc → project_id asc (third-tier tiebreak)
      4. Return first

    Returns None if no match — caller falls back to get_default().
    Note: Inbox (isDefault=true) typically has senderEmails=[], so it does NOT match
    here; it's reached via the get_default() fallback path.
    """

def get_default(uid: str) -> dict:
    """
    Returns the user's Inbox project. Auto-creates if missing — this is the
    side-effect that bootstraps Phase 1 for existing users on first watcher run.
    """

def add_sender_to_project(uid: str, project_id: str, sender_email: str) -> None:
    """Appends to senderEmails (de-duped, lowercased). Logs activity event."""

def remove_sender_from_project(uid: str, project_id: str, sender_email: str) -> None:
    """Removes from senderEmails. Logs activity event."""

def link_forum_group(
    uid: str,
    project_id: str,
    forum_chat_id: int,
    forum_group_title: str,
    linked_by_telegram_user_id: int,
    is_forum_enabled: bool,
) -> None:
    """
    Called from firestore_telegram.consume_link_token() after user runs /link
    in the target forum group. Sets forumChatId, isForumEnabled, linkedAt, etc.
    Logs project_linked activity event.
    """
```

**Constraints (enforced in wrappers, not Firestore rules)**:
- `create_project()` rejects creating a second `is_default=True` for the same uid.
- `archive_project()` rejects archiving when it's the only default — caller must create a replacement default first.
- Slug uniqueness checked on `create_project()` and `update_project()` when slug changes.
- `priority` clamped to `[0, 1000]` to keep ordering predictable.

### 6.2 `firestore_alerts.py`

Existing `_user_creds(uid)` returns `(token, chat_id)` for legacy single-chat routing. Extend to accept routing hints and return a richer destination object.

**New return type** (define in `firestore_alerts.py`):

```python
from dataclasses import dataclass

@dataclass
class AlertDestination:
    bot_token: str
    chat_id: int                  # forum_chat_id when is_legacy=False; legacy chatId when is_legacy=True
    topic_id: int | None          # None means General topic (or N/A in legacy mode)
    project_id: str | None        # for activity logging; None in legacy mode
    is_legacy: bool               # True = posting to legacy single chat, ignore topic_id
```

**Updated signatures**:

```python
def _user_creds(
    uid: str,
    sender_email: str | None = None,
    subject_slug: str | None = None,
    cleaned_subject: str | None = None,
) -> AlertDestination:
    """
    Resolves the routing destination for an alert.
    Routing precedence:
      1. If sender_email + subject_slug provided AND user has projects: do full
         project→forum→topic resolution (calls firestore_projects, firestore_folders,
         and may trigger telegram_topics.create_topic).
      2. Else if user has projects but no routing hints: route to default project's
         General topic (forum_chat_id, topic_id=None).
      3. Else (no projects yet, legacy user): return legacy AlertDestination
         using users/{uid}.telegram.chatId. is_legacy=True.

    Customer-bot fallback (users/{uid}.customerBot.token) is honored at all
    levels — it overrides bot_token but does not change chat_id resolution.
    """

def send_alert(
    uid: str,
    text: str,
    sender_email: str | None = None,
    subject_slug: str | None = None,
    cleaned_subject: str | None = None,
    parse_mode: str = "HTML",
) -> bool:
    """
    Resolves destination via _user_creds() and posts via bridge or direct
    requests call to the Bot API. Returns True on success.
    Failure path:
      - Telegram createForumTopic rate-limited → fallback to General, log warning
      - Bot blocked / kicked from group → log error, mark project.isForumEnabled=false,
        retry to legacy fallback if available
      - All paths fail → record in firestore_activity as alert_failed, return False
    """
```

**Behavior notes**:
- This function is the **single entry point** for routing. `watcher.py` and any other caller passes `(sender_email, subject_slug, cleaned_subject)`; nothing else needs to know about projects or topics.
- Existing legacy callers (tests, scripts) that call `send_alert(uid, text)` without routing hints continue to work via path (2) or (3).

### 6.3 `firestore_folders.py`

**Path change**: `users/{uid}/folders/{subject_slug}` → `users/{uid}/projects/{project_id}/folders/{subject_slug}`. All function signatures gain a `project_id` parameter immediately after `uid`.

**Updated signatures**:

```python
def get(uid: str, project_id: str, subject_slug: str) -> dict | None:
    """
    Returns folder dict or None. Performs lazy migration:
      - If not found at the new path AND a legacy doc exists at the old path
        users/{uid}/folders/{subject_slug}, the legacy doc is copied to the
        new path under the project_id passed by the caller (NOT necessarily Inbox),
        the old doc is deleted, and the migrated doc is returned.
      - This means: for an existing user whose sender was just assigned to project
        Acme, the first email under that subject migrates the legacy folder under
        Acme, not under Inbox. The "always migrate to Inbox" wording in earlier
        drafts of §5.2 is **superseded** by this clarified rule.
      - The nightly batch job in §7.3 sweeps any leftover legacy folders that
        haven't been touched and moves them under default_project_id.
    """

def upsert(uid: str, project_id: str, subject_slug: str, **fields) -> None:
    """Idempotent upsert. Validates topicState enum if provided."""

def list_for_project(
    uid: str,
    project_id: str,
    include_archived: bool = False,
) -> list[dict]:
    """All folders within a project. Sorted by lastEmailAt desc."""

def get_or_create_topic(
    uid: str,
    project_id: str,
    subject_slug: str,
    cleaned_subject: str,
    trigger: str,  # "priority" | "threshold" | "manual_pin"
) -> int:
    """
    Idempotent: if folder.topicId is set and topicState in (pinned, auto), returns it.
    Otherwise calls telegram_topics.create_topic() with project's forumChatId,
    persists topicId/topicState/topicCreatedAt, logs topic_created activity event.
    Raises ProjectNotLinkedError if the project's forumChatId is not set.
    Caller (firestore_alerts) catches and falls back appropriately.
    """

def archive_topic(uid: str, project_id: str, subject_slug: str) -> None:
    """
    Sets folder.topicState='archived', calls telegram_topics.close_topic().
    Logs topic_archived activity event. Telegram failure is logged but does not
    raise — Firestore state is the source of truth for routing.
    """

def pin_topic(
    uid: str,
    project_id: str,
    subject_slug: str,
    cleaned_subject: str | None = None,
) -> int:
    """
    Manual elevation by user. Creates topic if it doesn't exist (cleaned_subject required
    in that case), then sets topicState='pinned' and is_pinned=true on Telegram via
    telegram_topics.edit_topic(). Logs topic_pinned. Returns topic_id.
    """

def promote_topic(
    uid: str,
    project_id: str,
    subject_slug: str,
    cleaned_subject: str,
) -> int:
    """
    User-triggered promote from General to Auto-Active. Creates the topic and posts
    the courtesy pointer message ("Earlier messages in [General]"). Logs topic_promoted.
    """

def rename_topic(
    uid: str,
    project_id: str,
    subject_slug: str,
    new_name: str,
) -> None:
    """
    User-initiated rename from portal. Updates folder.topicNameOverride, then calls
    telegram_topics.edit_topic() with the new name to push the change to Telegram.
    No-op on Firestore if topicId is null (folder still in General). Logs topic_renamed.
    Telegram-side push failures (e.g., topic deleted) are logged but don't roll back
    the Firestore write — Firestore is the display source of truth.
    """
```

**Field semantics for AI agents**:
- The folder's existing `subject` field stores the **cleaned subject** (Re:/Fwd:/Fw: stripped, original casing preserved). It is *not* the raw original subject. Callers that need to pass `cleaned_subject` to a wrapper function but only have a `subject_slug` can read the folder doc and use `folder.subject`. This is what `pin_topic(cleaned_subject=None)` does internally when called without an explicit value.
- Slug computation: the existing `watcher.py:_subject_slug()` function should be moved to a shared utility module (e.g., `subject_utils.py`) in Phase 1 since the portal will need to compute slugs for user-typed subjects (Pin from scratch case). Current import path is `from watcher import _subject_slug` — leave the existing import working via re-export.

**Side effects** of `get_or_create_topic`, `archive_topic`, `pin_topic`, `promote_topic`, `rename_topic`: on every state-changing operation that affects routing or display, the function calls `firestore_leads.propagate_topic_change()` (§6.4) to update denormalized `topicId` on all leads under this folder. (Rename only updates name, not topicId, so it doesn't propagate.)

### 6.4 `firestore_leads.py`

**Lead key changes**: `lead_id = SHA1(project_id|sender_email|subject_slug)` (was `SHA1(sender_email|subject_slug)`).

**Updated `upsert_lead()`**:

```python
def upsert_lead(
    uid: str,
    project_id: str,           # NEW required arg
    sender_email: str,
    subject_slug: str,
    cleaned_subject: str,
    interaction_count_delta: int = 1,
    topic_id: int | None = None,  # NEW; denormalized from folder at write time
    **other_fields,
) -> str:
    """
    Returns lead_id. Computes lead_id = SHA1(project_id|sender_email|subject_slug).
    Sets projectId and topicId fields. Reads parent folder to backfill topicId
    if caller didn't pass it.
    """
```

**New function**:

```python
def propagate_topic_change(
    uid: str,
    project_id: str,
    subject_slug: str,
    new_topic_id: int | None,
    new_topic_state: str | None,
) -> int:
    """
    Called by firestore_folders on topic state changes (create/archive/pin/promote).
    Updates topicId field on all leads matching (uid, project_id, subject_slug).
    Returns count of leads updated.
    Implementation: query leads collection where projectId=X and subject_slug=Y,
    batch-write topicId. Idempotent.
    """
```

**Migration helper** (called once per uid by backfill script in §7.3):

```python
def _migrate_lead_keys(uid: str) -> int:
    """
    Reads all legacy leads at users/{uid}/leads/{old_id}, computes new lead_id
    using projectId from the (already-migrated) parent folder, writes to new id,
    deletes old. Idempotent. Returns count migrated.
    """
```

**Dual-read window during lead-key migration**

Until Backfill 3 (§7.3) completes for a given uid, the watcher will write new leads under `SHA1(project_id|sender|subject)` while existing leads still sit at `SHA1(sender|subject)`. A naive `upsert_lead()` reading only the new key would see "no existing lead" and create a duplicate.

**Required behavior**: `upsert_lead()` reads **both** keys until a per-user feature flag is set:

```python
def upsert_lead(uid: str, project_id: str, sender_email: str, subject_slug: str, ...) -> str:
    new_id = sha1(f"{project_id}|{sender_email}|{subject_slug}").hexdigest()
    new_ref = db.collection("users").document(uid).collection("leads").document(new_id)
    snap = new_ref.get()
    if snap.exists:
        # Common path post-migration.
        return _update_existing(new_ref, snap, ...)

    # Fallback: only consult legacy key while migration is in flight.
    if not _migration_done(uid):
        old_id = sha1(f"{sender_email}|{subject_slug}").hexdigest()
        old_ref = db.collection("users").document(uid).collection("leads").document(old_id)
        old_snap = old_ref.get()
        if old_snap.exists:
            # Promote in place: write to new_id, delete old_id, denormalize projectId.
            return _promote_legacy_lead(old_ref, old_snap, new_ref, project_id, ...)

    # Genuine new lead.
    return _create_new(new_ref, project_id, sender_email, subject_slug, ...)


def _migration_done(uid: str) -> bool:
    """Reads users/{uid}.flags.leadKeyMigrationDone (cached per-process)."""
```

**Flag lifecycle**:
1. Pre-deploy: `users/{uid}.flags.leadKeyMigrationDone` is unset → reads as `false` → dual-read path active.
2. Backfill 3 script (§7.3) processes a uid, then sets `users/{uid}.flags.leadKeyMigrationDone = true` as its **last** write for that uid.
3. After flag flips, subsequent `upsert_lead()` calls skip the legacy read. The next deploy can drop the dual-read code entirely once **all** uids report `leadKeyMigrationDone == true`.

**This eliminates the duplicate-lead window**. Without this, the spec's "Backfill 3 runs 1-2 days post-deploy" sequencing in §7.3 would produce a guaranteed window of duplicate lead docs for any sender + subject pair that emails again before the script runs.

### 6.5 `firestore_telegram.py`

**Link-token flow updated** to bind to a project at token creation.

```python
def create_link_token(
    uid: str,
    link_target_project_id: str,   # NEW required arg
    ttl_minutes: int = 60,
) -> tuple[str, str]:
    """
    Returns (token_id, short_code). The short_code is what the user types as
    /link {short_code} in their Telegram forum group. The token is bound to
    a specific project; consumption writes forumChatId/forumGroupTitle back
    to that project's doc.
    """

def consume_link_token(
    short_code: str,
    telegram_chat: dict,           # raw Telegram chat object from /link handler
    telegram_user_id: int,         # who ran /link
) -> ConsumeResult:
    """
    Verifies the token (not expired, not consumed). Detects forum status from
    telegram_chat.is_forum field. Calls firestore_projects.link_forum_group()
    with the linked project_id (from token doc) and the captured forum_chat_id.
    Marks the token consumed.

    ConsumeResult fields: success, projectId, errorReason (if !success).
    """
```

**New helpers**:

```python
def is_forum_enabled(telegram_chat: dict) -> bool:
    """Returns chat.type == 'supergroup' and chat.is_forum is True."""

def get_general_topic_id(chat_id: int) -> int | None:
    """
    Returns the General topic's message_thread_id (always 1 for forum groups
    per Telegram API as of 2024). May return None on API error; caller
    treats None as 'omit message_thread_id when posting' which Telegram
    interprets as General.
    """
```

### 6.6 `watcher.py`

Two changes; both small.

**Pass routing hints to alert dispatch**: at the existing `send_alert()` call sites (around lines 550–560 per code survey), `subject_slug` is already computed at line 585 — pass it plus `sender_email` and `cleaned_subject`:

```python
# Before (existing):
send_alert(uid, alert_text)

# After:
send_alert(
    uid,
    alert_text,
    sender_email=parsed.from_email.lower(),
    subject_slug=subject_slug,
    cleaned_subject=cleaned_subject,
)
```

**Initial Inbox auto-creation**: in `_run_for_user(uid)` (or wherever the per-user loop starts), call `firestore_projects.get_default(uid)` early. This auto-creates Inbox if missing, ensuring downstream routing always finds at least one project. The function is idempotent and cheap (1 Firestore read + 0 writes once Inbox exists).

Email parsing, PDF generation, and summary CSV logic are unchanged. **`subject_slug` computation gains one line**: when the existing `slugify`-style transform yields an empty string (CJK / non-ASCII subjects), return `f"subj-{sha1(cleaned_subject.encode('utf-8')).hexdigest()[:8]}"` instead of `"no-subject"`. See Q1 resolution.

### 6.7 NEW file: `telegram_topics.py`

Thin wrapper around Telegram Bot API endpoints for Forum Topic operations. Kept separate from `bridge.py` (python-telegram-bot handlers) because this file makes outbound API calls only — no event loop, no incoming-message handling. Pure functions, easy to mock in tests.

```python
import requests
from typing import Optional

# All functions raise TelegramError on non-2xx. Caller handles fallback.

def create_topic(
    chat_id: int,
    name: str,
    icon_color: int | None = None,
    icon_custom_emoji_id: str | None = None,
) -> int:
    """
    Calls Telegram Bot API: createForumTopic.
    Returns message_thread_id. Truncates name to 128 chars (Telegram limit).
    Retries with exponential backoff on 429 (rate limit) up to 3 times.
    Raises TopicCreateError on persistent failure.
    """

def edit_topic(
    chat_id: int,
    message_thread_id: int,
    name: str | None = None,
    icon_custom_emoji_id: str | None = None,
) -> None:
    """Calls editForumTopic. Used for renames after user-edited topicNameOverride."""

def close_topic(chat_id: int, message_thread_id: int) -> None:
    """Calls closeForumTopic. Used by archive_topic in firestore_folders."""

def reopen_topic(chat_id: int, message_thread_id: int) -> None:
    """Calls reopenForumTopic. Used if user un-archives via portal."""

def delete_topic(chat_id: int, message_thread_id: int) -> None:
    """
    Calls deleteForumTopic. PERMANENT — deletes message history.
    Currently NOT called by any Phase 1 flow. Reserved for future hard-delete UX
    behind a confirmation dialog. Listed here so AI agents don't confuse archive
    (close) with delete.
    """

def pin_message_in_topic(chat_id: int, message_thread_id: int, message_id: int) -> None:
    """Calls pinChatMessage with message_thread_id. Used for pinning anchor messages."""

def post_message_to_topic(
    chat_id: int,
    message_thread_id: int | None,    # None = General
    text: str,
    parse_mode: str = "HTML",
) -> int:
    """
    Calls sendMessage with message_thread_id. Returns the new message's id.
    Used by firestore_alerts.send_alert() as the actual posting primitive.
    """
```

**Rate limiting**: Telegram applies separate flood limits to `createForumTopic` (≤50/sec per bot, lower per chat). The wrapper implements basic exponential backoff (sleep `2^retry` seconds, max 3 retries). Production-grade queueing (Cloud Tasks etc.) is deferred — Phase 1 caller handles persistent failure by falling back to General topic.

**Error class**:

```python
class TelegramError(Exception):
    def __init__(self, status_code: int, description: str, retry_after: int | None = None):
        self.status_code = status_code
        self.description = description
        self.retry_after = retry_after  # Telegram's parameters.retry_after when 429

class TopicCreateError(TelegramError): ...
class TopicNotFoundError(TelegramError): ...   # raised when editing/closing a deleted topic
```

### 6.8 `bridge.py` — `/link` handler

The existing `bridge.py` hosts python-telegram-bot handlers for incoming Telegram messages. The `/link {shortCode}` command handler is extended to detect forum-group context and route to the right wrapper.

**Updated handler logic** (pseudocode for the existing `/link` handler):

```python
async def handle_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    short_code = parse_shortcode_from_message(update.message.text)
    chat = update.effective_chat                 # Telegram Chat object
    user_id = update.effective_user.id

    # Detect forum context: chat.type == "supergroup" and chat.is_forum is True
    is_forum = firestore_telegram.is_forum_enabled(chat.to_dict())

    if is_forum:
        result = firestore_telegram.consume_link_token(
            short_code=short_code,
            telegram_chat=chat.to_dict(),
            telegram_user_id=user_id,
        )
        if result.success:
            project = firestore_projects.get_project(result.uid, result.projectId)
            await update.message.reply_text(
                f"✅ Linked to project '{project['name']}'. "
                f"Topics will be auto-created here as new email subjects arrive."
            )
        else:
            await update.message.reply_text(f"❌ {result.errorReason}")
    else:
        # Legacy single-chat link path (preserved unchanged)
        firestore_telegram.consume_legacy_link_token(
            short_code=short_code,
            chat_id=chat.id,
            telegram_user_id=user_id,
        )
        await update.message.reply_text("✅ Linked. Alerts will arrive in this chat.")
```

**Branching rule**: forum groups (chat.type == "supergroup" AND chat.is_forum == True) → new project-aware path. Everything else (private chats, regular groups) → existing legacy path. **No existing legacy /link behavior changes.**

**Customer-bot users**: the handler runs inside whichever bot the user added — same handler code, different bot identity. The shared bot and customer bots both deploy the same handler. The reply messages should NOT hardcode "@YourBot"; portal templates the user-visible "@bot_username" earlier in the link flow.

### 6.9 `firestore_activity.py` — event emission map

The existing `firestore_activity.py` wrapper is **not modified**, but new event types are added by the wrappers that own their state changes. Mapping:

| Event type | Emitted by | When |
|---|---|---|
| `project_created` | `firestore_projects.create_project()` | After successful Firestore write |
| `project_archived` | `firestore_projects.archive_project()` | After successful Firestore write |
| `project_linked` | `firestore_projects.link_forum_group()` | After successful Firestore write |
| `sender_assigned_to_project` | `firestore_projects.add_sender_to_project()` | After successful Firestore write |
| `sender_removed_from_project` | `firestore_projects.remove_sender_from_project()` | After successful Firestore write |
| `topic_created` | `firestore_folders.get_or_create_topic()` | After Telegram createForumTopic + Firestore write succeed |
| `topic_archived` | `firestore_folders.archive_topic()` | After Firestore write (Telegram close best-effort) |
| `topic_pinned` | `firestore_folders.pin_topic()` | After Firestore write + anchor message pin |
| `topic_promoted` | `firestore_folders.promote_topic()` | After Firestore write |
| `topic_renamed` | `firestore_folders.rename_topic()` | After Firestore write |
| `topic_possible_collision` | `firestore_folders.upsert()` (Phase 3a) | When `senderFingerprint` mismatch detected |
| `alert_pending_link` | `firestore_alerts.send_alert()` | When routing returns `_LEGACY_FALLBACK` AND legacy chatId is also unset |
| `alert_failed` | `firestore_alerts.send_alert()` | When all delivery attempts fail (Telegram + legacy) |

Convention: every wrapper that mutates Firestore state and has an event-type listed above must emit the event in the same write batch where possible (atomic), or immediately after on best-effort. The activity event payload follows §5.1.7 schema. AI agents should NOT add ad-hoc event types not listed here; new events go through this spec.

### 7.1 Existing Users

**Principle: nobody breaks on deploy day.** Users with `users/{uid}.telegram.chatId` set continue to receive alerts at that chat with no behavior change. Forum routing is opt-in per project — until a user creates a project and links a forum group, alerts use the legacy path.

**Day-0 behavior**:
1. Deploy ships. No data migration runs synchronously.
2. First time `watcher.py:_run_for_user(uid)` executes after deploy, `firestore_projects.get_default(uid)` is called. If `users/{uid}/projects/` is empty, an Inbox project is created (`isDefault: true, forumChatId: null`). `users/{uid}.defaultProjectId` is set.
3. The watcher continues to call `send_alert(...)` with routing hints. `_user_creds()` resolves: Inbox exists, but Inbox has no `forumChatId` → falls back to legacy `users/{uid}.telegram.chatId`. **User sees identical behavior to pre-deploy.**
4. When the user logs into the portal, they see an in-app banner: *"You can now organize alerts into Projects. Set up your first project →"*. No forced action.

**Opt-in path**: user creates a project in portal → clicks "Link Telegram" on that project → follows the §7.2 link flow → from then on, emails matching that project's `senderEmails` route to the project's forum group; everything else stays in legacy chat (or goes to Inbox once Inbox is linked).

**Eventual consolidation**: once a user links any forum group (typically Inbox), the legacy `users/{uid}.telegram.chatId` is no longer the primary route — but it's preserved as a fallback for `Pending Link` scenarios (§4.4 failure modes). The portal offers a "disconnect legacy chat" button after Inbox is linked, but does not force removal.

### 7.2 Telegram Link Flow

The link flow binds a Telegram forum group to a specific project. It can run multiple times per user (one per project being linked).

**Sequence:**

```
1. Portal: user views Project (or creates new one)
   ┌─────────────────────────────────────────────┐
   │ Project: Acme Acquisition                   │
   │ Senders: [add senders]                      │
   │ Telegram: ⚠ Not linked  [ Link Telegram → ] │
   └─────────────────────────────────────────────┘

2. User clicks "Link Telegram"
   → Backend: firestore_telegram.create_link_token(uid, project_id)
   → Returns short_code (e.g., "ABC123")
   → Portal shows instructions:
     ┌──────────────────────────────────────────────────┐
     │ Linking "Acme Acquisition" to Telegram           │
     │                                                  │
     │ 1. In Telegram, create a new group              │
     │ 2. Group settings → enable "Topics"             │
     │ 3. Add @YourBot to the group as admin           │
     │ 4. In the group, send: /link ABC123             │
     │                                                  │
     │ Code expires in 60 minutes.                     │
     │ Status: Waiting...                              │
     └──────────────────────────────────────────────────┘

3. User does steps 1-3 in Telegram, then sends /link ABC123 in the group
   → Bot's command handler in bridge.py receives the update
   → handler calls firestore_telegram.consume_link_token(
       short_code="ABC123",
       telegram_chat=update.chat,         # has chat.id, chat.type, chat.is_forum, chat.title
       telegram_user_id=update.from_user.id,
     )
   → consume_link_token verifies:
     - token exists, not expired, not already consumed
     - chat.type == "supergroup" and chat.is_forum == True
     - if not forum-enabled: replies "❌ This group doesn't have Topics enabled.
       Enable in Group Settings → Topics, then try /link again."
   → On success: calls firestore_projects.link_forum_group() with project_id from token
   → Bot replies in the group's General topic:
     "✅ Linked to project 'Acme Acquisition'.
      Topics will be auto-created here as new email subjects arrive.
      Manage senders and pinned topics at <portal_url>/projects/<slug>"

4. Portal poll detects consumption → shows green check, lists forum group title
```

**Backwards compatibility**: the existing `/link {shortCode}` command in `bridge.py` continues to handle legacy single-chat link tokens (those with `linkTargetProjectId == null` for older tokens). The handler branches on `is_forum_link`:
- legacy single chat → write `users/{uid}.telegram.chatId` (existing behavior)
- forum group → call `firestore_projects.link_forum_group()` (new)

**Edge cases**:

| Scenario | Behavior |
|---|---|
| User runs `/link` in a non-forum group | Bot replies with the "enable Topics" instruction; token remains unconsumed and reusable |
| User runs `/link` in a private chat (not a group) | Falls through to legacy single-chat link path, binds `telegram.chatId` only |
| Link code expired | Bot replies "Link code expired. Generate a new one in the portal." |
| Same forum group linked to two projects (different `/link` runs) | Last write wins on `project.forumChatId`; previous project becomes unlinked. Portal warns before allowing this. |
| Same project linked to a *new* forum group (project.forumChatId already set, /link runs in a different group) | Old `forumChatId` is overwritten with the new group's id. **All folders under that project get `topicId=null` and `topicState=null`** because the saved topic IDs were `message_thread_id`s in the old chat and are now invalid. Portal warns and asks the user to confirm before consuming the token. After rebind, topics will be re-created lazily as new emails arrive. **Folder clears are issued in `WriteBatch` chunks of ≤500 ops** (Firestore's per-batch limit); on partial failure (network, auth, transient `gax` error mid-batch), the rebind emits an activity event `forum_rebind_partial` with payload `{projectId, oldChatId, newChatId, foldersCleared, foldersRemaining}`, and the portal exposes a "Resume rebind" CTA on the project detail page that re-runs the clearing pass over folders where `topicId IS NOT NULL`. The operation is idempotent — re-running it on a fully-cleared project is a no-op. |
| User removes the bot from the linked group | Detected on next alert dispatch failure (§4.4 failure modes); project flagged `isForumEnabled=false`, banner shown in portal |

### 7.3 Data Backfill

Three independent backfills, each idempotent and re-runnable.

**Backfill 1: Inbox project** (lazy, no script needed)

Trigger: `firestore_projects.get_default(uid)` is called from the watcher's per-user loop. If the user has no projects, Inbox is auto-created with the standard defaults (§5.2). One-time per uid, then no-op.

**Backfill 2: Folder path migration** (lazy + nightly batch)

Lazy path: `firestore_folders.get(uid, project_id, subject_slug)` checks both old path (`users/{uid}/folders/{subject_slug}`) and new path. If found at old, copies to new path under `default_project_id`, deletes old, returns migrated doc.

Nightly batch (`scripts/migrate_folders_under_projects.py`): iterates all uids, finds any leftover docs at the old path, runs the same migration. Logs per-uid progress. Safe to run repeatedly; each run is a no-op once complete.

**Important**: only the **doc data** is moved. The on-disk PDF folder at `~/email-pdfs/{uid}/{subject-slug}/` is **not** touched — paths stay the same on disk. Phase 2 may add a project subdirectory, but Phase 1 keeps the disk layout to avoid coordinating two migrations at once.

**Backfill 3: Lead key migration** (one-time script)

Existing leads use `lead_id = SHA1(sender_email|subject_slug)`. New leads use `SHA1(project_id|sender_email|subject_slug)`. Migration script (`scripts/migrate_lead_keys.py`):

```
For each uid:
  1. firestore_projects.get_default(uid) → inbox_id (auto-creates if needed)
  2. For each lead under users/{uid}/leads/{old_id}:
     - Read parent folder's project_id (must be migrated first via Backfill 2)
     - Compute new_id = SHA1(project_id|sender_email|subject_slug)
     - If old_id == new_id: skip (already correct, can happen on re-run)
     - Write doc to users/{uid}/leads/{new_id} with projectId field set
     - Delete users/{uid}/leads/{old_id}
  3. Log per-uid count
```

Order of operations on first deploy: Backfill 1 runs lazily as users hit the watcher → Backfill 2 runs lazily on first folder access → Backfill 3 is run **once** as a manual job after the deploy stabilizes (typically 1-2 days post-deploy when traffic is light).

**Dual-read protection during the Backfill-3 window**: between deploy and Backfill 3 completing for a given uid, `firestore_leads.upsert_lead()` is required to consult both the new and the legacy key (see §6.4 "Dual-read window"). Backfill 3 sets `users/{uid}.flags.leadKeyMigrationDone = true` as its last write per uid, which retires the legacy read. The dual-read path can be deleted in a subsequent deploy once all uids report `leadKeyMigrationDone == true`.

**`emailCount` is NOT backfilled**: per §5.2, this is intentional. Only post-deploy emails count toward auto-create thresholds. If a user wants legacy heavy-traffic subjects elevated, they Pin them manually in the portal.

**Verification queries** (run after each backfill):

```
# Backfill 2 check: any leftover legacy folders?
SELECT COUNT(*) FROM users/{uid}/folders WHERE __name__ != "<placeholder>"
# Should be 0 once batch completes

# Backfill 3 check: any leads without projectId?
SELECT COUNT(*) FROM collectionGroup("leads") WHERE projectId == null
# Should be 0 once script completes
```

## 8. Phased Rollout

### Phase 1: Forum Topics Infrastructure (1–2 weeks)

Backend-only. No portal changes; all setup goes through manual Firestore writes and Telegram for now. The goal is end-to-end routing working for a single test user before exposing UX in Phase 2.

**Acceptance:**
- [ ] `firestore_projects.py` implemented with all functions in §6.1; unit tests for each
- [ ] `telegram_topics.py` implemented with mocks for Telegram API; rate-limit retry tested
- [ ] `firestore_alerts.py` extended with `AlertDestination` dataclass and 3-tier routing (forum → default project General → legacy)
- [ ] `firestore_folders.py` path nested under projects; lazy migration helper passing test against pre-spec docs
- [ ] `firestore_leads.py` upsert uses new SHA1 key, denormalizes `projectId` and `topicId`
- [ ] `firestore_telegram.py` link flow accepts `linkTargetProjectId`; `consume_link_token` writes to project doc
- [ ] `bridge.py` `/link` handler routes forum-group consumption to project; preserves legacy single-chat path
- [ ] `watcher.py` passes `sender_email`, `subject_slug`, `cleaned_subject` to every `send_alert` call site
- [ ] Watcher calls `firestore_projects.get_default(uid)` once per user-loop entry (auto-creates Inbox)
- [ ] All new event types from §5.1.7 written to `firestore_activity` correctly
- [ ] **End-to-end smoke test on Shawn's account**:
  1. Manually create a "Test" project with one sender email
  2. Manually link a Telegram forum group via `/link`
  3. Send an email from the configured sender with subject "Test 1" — verify message arrives in General topic of the linked group
  4. Send a 2nd email with same subject — verify a topic "Test 1" auto-created and message routed there
  5. Send an email from a non-configured sender — verify it routes to Inbox (which falls back to legacy chat since Inbox isn't linked yet)
- [ ] Legacy user behavior verified: a user with no projects continues receiving alerts at `users/{uid}.telegram.chatId` with zero behavior change
- [ ] Backfill scripts (`migrate_folders_under_projects.py`, `migrate_lead_keys.py`) written but not yet run

**Out of scope for Phase 1**: portal UI, sender bulk-import, multi-project link wizard, project archiving UI.

### Phase 2: Portal UI for Project & Topic Management (1 week)

Surface what Phase 1 built. No new backend logic except thin endpoints that wrap existing wrappers.

**Acceptance:**
- [ ] **Projects list page**: create new project, see linked status (✅/⚠), archive (with confirmation), reorder by priority
- [ ] **Project detail page**: name + slug edit, sender list (add/remove), Link Telegram CTA with live polling, topic list with state pills, last-email timestamps
- [ ] **Topic actions**: Pin, Archive, Promote-from-General, Rename, all with confirmation dialogs
- [ ] **Activity feed**: chronological list of project + topic events from `users/{uid}/activity`, filterable by project
- [ ] **Legacy-user banner**: first-login prompt to create a project, with a "Skip for now" option
- [ ] **Backend endpoints** (REST or RPC, existing portal pattern):
  - `POST /api/projects` → `firestore_projects.create_project`
  - `PATCH /api/projects/{id}` → `update_project`
  - `POST /api/projects/{id}/archive` → `archive_project`
  - `POST /api/projects/{id}/senders` / `DELETE` → `add_sender_to_project` / `remove_sender_from_project`
  - `POST /api/projects/{id}/link-token` → `firestore_telegram.create_link_token`
  - `POST /api/projects/{id}/topics/{slug}/pin|archive|promote|rename` → `firestore_folders.*`
- [ ] Run lead-key backfill script in production after a quiet window

**Out of scope for Phase 2**: collision detection, threading, RAG.

### Phase 3: Threading & Collision Guardrail (data-driven decision)

Phase 3 is conditional. The goal is to instrument first, decide later, based on real user data.

**Acceptance — Phase 3a (always ship, low cost):**
- [ ] Add a `senderFingerprint` field on folder docs: SHA1 of the first sender's email domain. Updated on every email — if incoming email's sender domain doesn't match the fingerprint, increment a `collisionWarnings` counter on the folder.
- [ ] Portal surfaces a "⚠ Possible collision" badge on folders where `collisionWarnings > 0`
- [ ] Activity event `topic_possible_collision` emitted with payload `{projectId, subject_slug, originalDomain, newDomain, senderEmail}`

**Acceptance — Phase 3b (conditional on data):**
- [ ] After 4 weeks of Phase 3a data, calculate collision rate: `(folders with collisionWarnings > 0) / (total folders)` per user
- [ ] **Decision rule**: if median user collision rate exceeds 5%, implement full Message-ID / References / In-Reply-To threading. Otherwise, close Phase 3 as "monitoring is sufficient" and document the data.
- [ ] If implementing threading: separate spec doc; touches `watcher.py` email parsing only, does not change topic routing model.

### Phase 4: Folder-scoped RAG (deferred — out of scope for this spec)

Placeholder. Covered in a separate future spec. This Phase 1 design is **RAG-ready** in two ways:

1. The path `users/{uid}/projects/{project_id}/folders/{subject_slug}` provides a natural unit for vector indexes. RAG can attach `vectorIndexId` on either the project or folder doc without schema collision.
2. Telegram bot already has chat/topic context (`chat_id`, `message_thread_id`) when a user replies to it — RAG can use these to scope retrieval to the matching project/folder without inventing a new mapping.

The next spec will decide: project-scoped RAG (one index per project) vs. subject-scoped (one index per folder) vs. hybrid.

Each item is a real unresolved decision that doesn't block Phase 1 ship but needs an answer at a known checkpoint. Format: question, why it matters, decide-by.

**Q1 — CJK / Korean subject handling.** **RESOLVED (pre-freeze).** Current `_subject_slug()` strips non-ASCII, collapsing every Korean subject to `"no-subject"` and producing catastrophic per-user collisions. **Resolution**: when `slugify(cleaned_subject)` returns an empty string, fall back to `f"subj-{sha1(cleaned_subject.encode('utf-8')).hexdigest()[:8]}"`. Two messages with the same original subject yield the same slug; different non-ASCII subjects yield different slugs. The fallback is required wherever slug is computed — `watcher.py:_subject_slug()` today, the shared utility module called out in §6.3 once it exists, and any portal-side slug computation. **Acceptance**: a Korean subject and a Japanese subject produce two different folder paths; two emails with the same Korean subject share one folder. *No further decision needed.*

**Q2 — Sender email canonicalization.** Are `alice+tag@example.com` and `alice@example.com` the same person for project-membership matching? Recommendation: lowercase always; do **not** strip `+tag` (it can be intentional routing). Decide explicitly so AI agents implementing `find_for_sender()` don't have to guess. *Decide by Phase 1 design freeze.*

**Q3 — Bot removal recovery UX.** When a user kicks the bot from a linked forum group, alerts fail. Auto re-invite is intrusive ("creepy bot keeps coming back"); manual reconnect via portal is cleaner. Recommendation: portal "Reconnect" CTA on the project detail page. *Decide by Phase 2.*

**Q4 — Welcome anchor message on first link.** When a project's forum group is freshly linked, its General topic is empty. Should the bot post a "Welcome to {Project}. Topics will appear here as emails arrive." anchor? Pro: orientation. Con: clutter. Recommendation: yes, but make it a single pinned message that doesn't notify members. *Decide by Phase 2 portal copy.*

**Q5 — Topic name renames propagation.** If user edits topic name in Telegram (not portal), do we sync back to `topicNameOverride`? If user edits in portal, do we push to Telegram via `editForumTopic`? Recommendation: portal → Telegram is one-way push; Telegram → Firestore is best-effort sync via webhook. *Decide by Phase 2.*

**Q6 — Activity event retention.** `users/{uid}/activity` grows unbounded. Set a Firestore TTL field with reasonable retention (recommendation: 90 days for most events, never-expire for `project_*` and `topic_created`). *Decide by Phase 2 end.*

**Q7 — Telegram rate limit handling at scale.** Current `telegram_topics.py` does exponential backoff up to 3 retries. A user adding 50 senders that immediately get auto-created topics could exceed Telegram's per-bot 50 topics/sec budget. Queue (Cloud Tasks) vs. throttle in-process? Recommendation: monitor in Phase 1, build queue only if observed in production. *Decide based on Phase 1 metrics.*

**Q8 — Multi-Telegram-account per user.** User has personal + work Telegram and wants different projects routed to each. Current model assumes one Telegram account per uid. Likely Phase 5 work. *Defer.*

**Q9 — Cross-project topic move.** User accidentally puts a sender in the wrong project; topics auto-create in the wrong forum group. How to migrate? Recommendation: manual support intervention in Phase 1; portal "Move to Project" button in Phase 3+ once we understand frequency. *Defer.*

**Q10 — Project hard-delete.** Spec only has archive. Should there ever be a permanent delete that wipes folders/leads/topics? Recommendation: never automatic; offer 30-day-after-archive purge as opt-in for users who want it. *Defer.*

---

## Appendix A: References

- Memory: `project_email2ppt_subject_topics.md` — architectural decisions log
- Memory: `project_email2ppt_architecture.md` — codebase baseline
- Telegram Bot API — Forum Topics: https://core.telegram.org/bots/api#forum-topic
- Existing code paths surveyed:
  - `firestore_alerts.py:_user_creds()` (lines 40–85)
  - `watcher.py:_subject_slug()` (lines 361–367)
  - `firestore_folders.py` — folder CRUD
  - `firestore_leads.py` — lead upsert with subject_slug dedup

## Appendix B: Glossary

- **Project**: Named cluster of email senders that maps 1:1 to a Telegram Forum group. Each user has one or more projects; one is always the default "Inbox" project that catches unmatched senders.
- **Inbox project**: The default project (`isDefault: true`) auto-created at first watcher run. Catches emails from senders not assigned to any specific project.
- **Forum group**: A Telegram supergroup with the "Topics" feature enabled. Linked to exactly one project per uid.
- **Forum topic**: Sub-thread within a Forum group. Each has a unique `message_thread_id` (referred to as `topic_id` in this spec). Topics are scoped to one project's forum group.
- **General topic**: The default unnamed topic in every Forum group (Telegram-provided). Fallback destination when no per-subject topic is resolved.
- **subject_slug**: Lowercase URL-safe transformation of email subject after stripping Re:/Fwd:/Fw: prefixes. Used as Firestore folder key and filesystem folder name. Generated by `watcher.py:_subject_slug()`. This spec adds a single empty-slug fallback for CJK / non-ASCII subjects: when `slugify()` returns empty, use `f"subj-{sha1(cleaned_subject.utf8)[:8]}"` (see Q1 resolution).
- **cleaned_subject**: The email subject with Re:/Fwd:/Fw: prefixes removed but original casing preserved. Used as the *display name* of a Forum topic. Distinct from `subject_slug`, which is the routing key.
- **Pinned topic**: User-designated VIP subject. Created proactively (without waiting for the threshold), visually pinned in the Telegram forum group. State: `topicState="pinned"`.
- **Auto-Active topic**: Topic auto-created after a trigger fired (priority sender or threshold reached). State: `topicState="auto"`.
- **Archived topic**: User-archived subject. Closed in Telegram (`is_closed: true`); new emails route to the project's General topic. State: `topicState="archived"`.
- **priorityWatchSenders**: Existing per-user flat list of email addresses whose messages get elevated treatment. In this spec: their first email of a new subject within their project triggers immediate auto-create (no threshold wait). Does not override project membership.
- **Promote**: User action to elevate a subject from General topic to its own dedicated topic. Future-only — past messages remain in General (Telegram API limitation).
- **`linkTargetProjectId`**: Field on a `telegram_link_tokens` doc, set at token creation, indicating which project the `/link` command will bind to when the user runs it in a forum group.
