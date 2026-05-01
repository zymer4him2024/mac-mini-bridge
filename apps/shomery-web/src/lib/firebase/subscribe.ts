import {
  onSnapshot,
  type DocumentData,
  type DocumentReference,
  type FirestoreError,
  type Query,
  type QuerySnapshot,
  type DocumentSnapshot,
} from "firebase/firestore";

const PERMISSION_DENIED_RETRY_DELAYS_MS = [500, 1000, 1500];

type Subscribable<T> = T extends Query<infer U>
  ? { ref: Query<U>; snap: QuerySnapshot<U> }
  : T extends DocumentReference<infer U>
    ? { ref: DocumentReference<U>; snap: DocumentSnapshot<U> }
    : never;

/**
 * onSnapshot that retries on permission-denied during the auth-token bootstrap
 * window. After a fresh sign-in, Firestore's long-lived listener stream can
 * race the ID token; the read fails with permission-denied and the SDK
 * destroys the listener. Retrying with short backoff lets the listener
 * re-attach once the token has propagated.
 */
export function subscribeWithRetry<
  R extends Query<DocumentData> | DocumentReference<DocumentData>,
>(
  ref: R,
  onNext: (snap: Subscribable<R>["snap"]) => void,
  onError?: (err: FirestoreError) => void,
): () => void {
  let cancelled = false;
  let unsub: (() => void) | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;

  const attach = () => {
    if (cancelled) return;
    unsub = onSnapshot(
      ref as Query<DocumentData>,
      ((snap: QuerySnapshot<DocumentData>) =>
        onNext(snap as unknown as Subscribable<R>["snap"])) as (
        snap: QuerySnapshot<DocumentData>,
      ) => void,
      (err) => {
        if (
          err.code === "permission-denied" &&
          attempt < PERMISSION_DENIED_RETRY_DELAYS_MS.length &&
          !cancelled
        ) {
          const delay = PERMISSION_DENIED_RETRY_DELAYS_MS[attempt];
          attempt += 1;
          retryTimer = setTimeout(attach, delay);
          return;
        }
        if (onError) onError(err);
        else console.error("Snapshot listener error", err);
      },
    );
  };

  attach();
  return () => {
    cancelled = true;
    if (retryTimer) clearTimeout(retryTimer);
    unsub?.();
  };
}
