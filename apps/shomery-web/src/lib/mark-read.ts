"use client";

import {
  doc,
  runTransaction,
  serverTimestamp,
} from "firebase/firestore";

import { getFirebaseDb } from "@/lib/firebase/client";

/**
 * Mark a folder item as read on first open. Sets `readAt` on the item and
 * decrements the parent folder's `unreadCount` (clamped to >= 0) in a single
 * transaction. No-ops if the item is already read or the item is missing.
 */
export async function markItemRead(
  uid: string,
  slug: string,
  itemId: string,
): Promise<void> {
  const db = getFirebaseDb();
  const itemRef = doc(db, `users/${uid}/folders/${slug}/items/${itemId}`);
  const folderRef = doc(db, `users/${uid}/folders/${slug}`);

  await runTransaction(db, async (tx) => {
    const itemSnap = await tx.get(itemRef);
    if (!itemSnap.exists()) return;
    if (itemSnap.data().readAt) return;

    const folderSnap = await tx.get(folderRef);
    tx.update(itemRef, { readAt: serverTimestamp() });
    if (folderSnap.exists()) {
      const current = Number(folderSnap.data().unreadCount ?? 0);
      if (current > 0) {
        tx.update(folderRef, { unreadCount: current - 1 });
      }
    }
  });
}
