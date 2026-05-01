# Shomery — Data Model

Canonical TypeScript types live in `shared/types/`, imported via `@shomery/shared-types`. This doc explains the model; the `.ts` file is the source of truth.

## Core types

```typescript
type Subject = {
  subject_slug: string;       // immutable routing key, derived from email subject
  display_name: string;       // user-editable, defaults to subject_slug
  uid: string;                // tenant
  group_id: string | null;    // null when ungrouped
  unread_count: number;
  last_email_at: Timestamp;
};

type Group = {
  group_id: string;
  name: string;               // user-named, e.g. "Acme Deal"
  uid: string;
  subject_slugs: string[];    // child subjects (immutable routing keys)
};

type EmailSummary = {
  id: string;
  subject_slug: string;       // home subject
  uid: string;
  sender_name: string;
  sender_email: string;
  subject: string;            // raw subject line
  received_at: Timestamp;
  priority: "low" | "medium" | "high";
  summary_bullets: string[];           // 2–5 bullets
  extracted: {
    intent?: string;
    action?: string;
    budget?: string;
    timeline?: string;
  };
  original_excerpt: string;            // first ~600 words of body
  gmail_thread_id: string;
  embedding_version: string;            // for re-indexing on model upgrade
  summary_model: string;                // audit trail
  attachments: Attachment[];
};

type Attachment = {
  filename: string;
  mime_type: string;
  caption: string | null;     // from the multimodal vision pipeline
};

type ChannelConfig = {
  uid: string;
  email_digest: { enabled: boolean; frequency: "each" | "daily" | "weekly" };
  kakaotalk: { connected: boolean; kakao_user_id?: string };
  whatsapp:  { connected: boolean; phone_number?: string };
  telegram:  { connected: boolean; chat_id?: string };
  sms:       { connected: boolean; phone_number?: string };
};

type ExcludedSource = {
  uid: string;
  scope: { type: "subject" | "group" | "global"; id: string | null };
  sender_email: string;
  excluded_at: Timestamp;
};
```

## Firestore paths

The actual paths are configured in `firestore.rules`. The shape is:

| Path | Type |
|---|---|
| `users/{uid}/subjects/{subject_slug}` | `Subject` |
| `users/{uid}/groups/{group_id}` | `Group` |
| `users/{uid}/emails/{email_id}` | `EmailSummary` |
| `users/{uid}/channelConfig` | `ChannelConfig` (single doc) |
| `users/{uid}/excludedSources/{id}` | `ExcludedSource` |

Storage (pre-Drive-verification):

| Path | Content |
|---|---|
| `summaries/{uid}/{subject_slug}/{email_id}.md` | The markdown artifact |

## Invariants

- **`subject_slug` is immutable.** Renaming a subject changes `display_name`, not `subject_slug`. Routing always uses `subject_slug`.
- **`group_id` is null until grouped.** Adding/removing a subject from a group only updates `subject.group_id` and `group.subject_slugs[]`. Emails never move.
- **`embedding_version` is recorded on every `EmailSummary`.** Mismatched versions in retrieval = bug; the registry must refuse mixed indices.
- **A subject is in zero or one groups.** Never multiple. Enforced by the single `group_id` field.

## Per-PR data model changes

When you change one of these types, the change ripples to:

- `shared/types/` (source of truth)
- `firestore.rules` (security)
- The Python pipeline (writers must produce conforming objects)
- Any existing data (migration script if shape is incompatible)

Always update all four in the same PR. Otherwise the schema drifts.
