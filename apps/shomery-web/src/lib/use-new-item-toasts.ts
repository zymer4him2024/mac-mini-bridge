"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { FolderItem } from "@shomery/shared-types";
import {
  collectionGroup,
  limit,
  orderBy,
  query,
  where,
} from "firebase/firestore";

import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";

const TOAST_AUTO_DISMISS_MS = 6000;
const QUERY_LIMIT = 50;

export interface NewItemToast {
  id: string;
  item: FolderItem;
}

export interface UseNewItemToastsResult {
  toasts: NewItemToast[];
  dismiss: (id: string) => void;
}

/**
 * Subscribes to the user's items and emits a toast for each new arrival
 * after first mount. The first snapshot is treated as silent baseline so
 * historical items don't all toast at once on page load.
 */
export function useNewItemToasts(uid: string | null): UseNewItemToastsResult {
  const [toasts, setToasts] = useState<NewItemToast[]>([]);
  const seenIds = useRef<Set<string>>(new Set());
  const isFirstSnapshot = useRef(true);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  useEffect(() => {
    if (!uid) return;

    isFirstSnapshot.current = true;
    seenIds.current = new Set();
    const localTimers = timers.current;

    const q = query(
      collectionGroup(getFirebaseDb(), "items"),
      where("uid", "==", uid),
      orderBy("createdAt", "desc"),
      limit(QUERY_LIMIT),
    );

    const unsub = subscribeWithRetry(q, (snap) => {
      if (isFirstSnapshot.current) {
        snap.docs.forEach((d) => seenIds.current.add(d.id));
        isFirstSnapshot.current = false;
        return;
      }
      const newOnes: NewItemToast[] = [];
      snap.docs.forEach((d) => {
        if (!seenIds.current.has(d.id)) {
          seenIds.current.add(d.id);
          newOnes.push({ id: d.id, item: d.data() as FolderItem });
        }
      });
      if (newOnes.length === 0) return;
      setToasts((prev) => [...newOnes, ...prev]);
      newOnes.forEach((t) => {
        const timer = setTimeout(() => dismiss(t.id), TOAST_AUTO_DISMISS_MS);
        localTimers.set(t.id, timer);
      });
    });

    return () => {
      unsub();
      localTimers.forEach((t) => clearTimeout(t));
      localTimers.clear();
    };
  }, [uid, dismiss]);

  return { toasts, dismiss };
}
