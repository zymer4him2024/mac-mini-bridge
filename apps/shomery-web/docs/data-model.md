# Shomery — Data Model

The schema lives in `shared/types/` and mirrors what the Python pipeline writes (`firestore_folders.py`, `firestore_users.py`). Both apps import from there; the compile breaks when the schema drifts.

The pipeline writes a per-folder, per-item shape — not a flat `email_summaries` collection. The web Feed reads items via a collection-group query filtered by `uid`.

## Current types

```typescript
// users/{uid}/folders/{subjectSlug}
type Folder = {
  subject: string;
  subjectSlug: string;                 // immutable routing key
  folderPath: string;
  pdfCount: number;
  hasSummaryCsv: boolean;
  createdAt: Timestamp;
  updatedAt: Timestamp;
  summaryCsvStoragePath?: string;
};

// users/{uid}/folders/{subjectSlug}/items/{itemId}
type FolderItem = {
  uid: string;                         // denormalized for collection-group query + security rules
  folderSubject: string;
  folderSlug: string;
  date: string;                        // free-form email date header
  from: string;                        // free-form "Name <addr@example.com>"
  urgency: "low" | "med" | "high";
  keyPoints: string[];                 // 2–5 bullets
  asks: string[];
  suggestedResponse: string;
  pdfFilename: string;
  createdAt: Timestamp;
  pdfStoragePath?: string;
  markdownStoragePath?: string;        // v1 markdown seam (Storage). Future: drive:// URI.
};

// users/{uid} — identity. Web client writes the five fields below on sign-in.
// Python (admin SDK) writes the gmail.* subtree separately; rules forbid the web client from touching it.
type UserIdentity = {
  email: string;
  displayName: string;
  photoURL: string;
  createdAt: Timestamp;
  lastSignedInAt: Timestamp;
  onboardingCompletedAt?: Timestamp;   // gates /feed and /subjects/*; set on "Start watching"
};

// users/{uid}/config/main — runtime config consumed by Python.
// Web writes specific fields; rules allow only the documented allowlist.
type UserConfig = {
  priorityWatchSenders: string[];       // written by Watched senders editor
  watcherLookback: string;
  digestEnabled: boolean;               // written by Notifications editor
  telegramEnabled: boolean;             // written by Notifications editor
  telegramChatId?: string;              // written by Notifications editor
  userDisplayName: string;
  retentionDays: number;
  summaryPersona: string;
  summaryKeyPointsMax: number;
  summaryAsksMax: number;
  intervalMinutes: number;
};

// users/{uid}/groups/{groupId} — virtual subject groupings, owned by the web app.
// A subject (folder slug) belongs to zero or one groups. Grouping does not
// move emails or rewrite the folder docs — only the parent reference changes.
type Group = {
  groupId: string;
  name: string;
  subjectSlugs: string[];               // membership list; "in zero or one groups" enforced client-side
  createdAt: Timestamp;
  updatedAt: Timestamp;
};
```

## Deferred models (added when their PR ships)

- **`Subject`** — today, "subject" is implemented as a `Folder`. An explicit `Subject` type arrives when the Subjects PR ships. (`Group` now lives in *Current types* — see above.)
- **`ChannelConfig`** — added when the second notification channel beyond Telegram lands. Until then, the relevant fields live on `UserConfig` (`digestEnabled`, `telegramEnabled`, `telegramChatId`).
- **Markdown artifact metadata** — once the watcher emits `.md`, each `FolderItem` carries `markdownStoragePath`. Pre-Drive-verification this points at Firebase Storage (`summaries/{uid}/{slug}/{itemId}.md`). Post-Drive, it becomes a `drive://...` URI. The web read goes through `getMarkdown(item)` — single switch point.

## Reading the data

- **Feed.** Collection-group query on `items` filtered by `uid == request.auth.uid`, ordered by `createdAt desc`, limit 50. Real-time via `onSnapshot()`.
- **Subject detail.** Collection on `users/{uid}/folders/{slug}/items` ordered by `createdAt desc`.
- **Markdown body.** `getMarkdown(item)` helper resolves `markdownStoragePath` and reads via the appropriate backend (Storage today, Drive later). This is the single switch point for the future Drive backend swap.

## Writing rules

- The web client writes only what's explicitly allowed by Firestore rules. The five identity fields on `users/{uid}` (plus `onboardingCompletedAt` after onboarding) and the documented allowlist on `users/{uid}/config/main` are the only paths the web SDK touches.
- `users/{uid}/groups/{groupId}` is owned by the web app. Rules require `groupId == request.resource.data.groupId`, validate `name` (non-empty, ≤50 chars) and `subjectSlugs` (string array, ≤100 entries), and gate read/write on `request.auth.uid == uid`. The "subject in zero or one groups" invariant is enforced client-side in the `useGroups` hook via batched cross-group writes — Firestore rules cannot express it.
- The `gmail.*` subtree on `users/{uid}` and the `folders/*` collection are owned by the Python pipeline (admin SDK). Rules forbid client writes.
- Cloud Functions running with admin SDK can write more broadly but should still go through `firestore_*.py` wrappers when interacting with pipeline-written collections (KMS, audit, redaction).

## Schema drift discipline

- TypeScript types are the contract for the web app. When Python adds a field, the TypeScript type adds it too — both apps stay in sync via `shared/types/`.
- Every embedding has its `embeddingVersion` recorded. Mixing vectors from different embedding models is a known footgun — the registry refuses cross-version reads.
- Pre-launch one-time migrations: rename any Firestore documents, slugs, or storage paths containing `pipelane` to `shomery`. Track on the launch checklist.
