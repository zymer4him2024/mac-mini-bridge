"use client";

import { useEffect, useState } from "react";

import {
  collectionGroup,
  limit,
  orderBy,
  query,
  where,
  type Timestamp,
} from "firebase/firestore";

import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";

export type LastSummaryState =
  | { status: "loading" }
  | { status: "none" }
  | { status: "ok"; at: Date };

export function useLastSummary(uid: string | null): LastSummaryState {
  const [state, setState] = useState<LastSummaryState>({ status: "loading" });

  useEffect(() => {
    if (!uid) {
      setState({ status: "loading" });
      return;
    }
    const q = query(
      collectionGroup(getFirebaseDb(), "items"),
      where("uid", "==", uid),
      orderBy("createdAt", "desc"),
      limit(1),
    );
    return subscribeWithRetry(q, (snap) => {
      const first = snap.docs[0];
      if (snap.empty || !first) {
        setState({ status: "none" });
        return;
      }
      const data = first.data() as { createdAt?: Timestamp };
      const ts = data.createdAt;
      if (ts && typeof ts.toDate === "function") {
        setState({ status: "ok", at: ts.toDate() });
      } else {
        setState({ status: "none" });
      }
    });
  }, [uid]);

  return state;
}
