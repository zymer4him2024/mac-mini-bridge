/**
 * Canonical TypeScript types for the Shomery data model.
 * Mirrors what the Python pipeline writes to Firestore.
 *
 * Source of truth: firestore_folders.py and firestore_users.py in the repo root.
 * The web app reads these shapes; Python (admin SDK) is the only writer for
 * folder/item docs.
 */

import type { Timestamp } from "firebase/firestore";

export type Locale = "en" | "ko" | "pt-BR";

export type Urgency = "low" | "med" | "high";

/** users/{uid}/folders/{subjectSlug} */
export interface Folder {
  subject: string;
  subjectSlug: string;
  folderPath: string;
  pdfCount: number;
  hasSummaryCsv: boolean;
  createdAt: Timestamp;
  updatedAt: Timestamp;
  summaryCsvStoragePath?: string;
}

/** users/{uid}/folders/{subjectSlug}/items/{itemId} */
export interface FolderItem {
  /** Denormalized for collection-group query + per-tenant security rules. */
  uid: string;
  folderSubject: string;
  folderSlug: string;
  /** Email date header, free-form string from the source message. */
  date: string;
  /** Sender, free-form "Name <addr@example.com>" string. */
  from: string;
  urgency: Urgency;
  keyPoints: string[];
  asks: string[];
  suggestedResponse: string;
  pdfFilename: string;
  createdAt: Timestamp;
  pdfStoragePath?: string;
  /**
   * v1 storage seam: a Firebase Storage path under
   * `summaries/{uid}/{subjectSlug}/{emailId}.md`.
   * After Drive verification clears, this becomes a `drive://...` URI; the
   * `getMarkdown()` helper is the single switch point.
   */
  markdownStoragePath?: string;
}

/**
 * users/{uid} — top-level identity doc.
 *
 * The web client owns the identity-only fields (email, displayName, photoURL,
 * createdAt, lastSignedInAt) and writes them on sign-in. The Python pipeline
 * (admin SDK) writes the gmail.* subtree during the Gmail OAuth handshake;
 * those fields are not represented here because the web client never touches
 * them and Firestore rules forbid it from doing so.
 */
export interface UserIdentity {
  email: string;
  displayName: string;
  photoURL: string;
  createdAt: Timestamp;
  lastSignedInAt: Timestamp;
}

/**
 * users/{uid}/config/main — per-user runtime config consumed by the Python
 * pipeline. The web app may write priorityWatchSenders, digestEnabled,
 * telegramEnabled, and telegramChatId; everything else is owned by Python.
 */
export interface UserConfig {
  priorityWatchSenders: string[];
  watcherLookback: string;
  digestEnabled: boolean;
  telegramEnabled: boolean;
  telegramChatId: string;
  userDisplayName: string;
  retentionDays: number;
  summaryPersona: string;
  summaryKeyPointsMax: number;
  summaryAsksMax: number;
  intervalMinutes: number;
}
