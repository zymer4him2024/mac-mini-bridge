"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  type User,
} from "firebase/auth";
import {
  doc,
  getDoc,
  onSnapshot,
  serverTimestamp,
  setDoc,
} from "firebase/firestore";

import { getFirebaseAuth, getFirebaseDb } from "@/lib/firebase/client";

export type AuthStatus = "loading" | "signed-in" | "signed-out";

export interface AuthState {
  user: User | null;
  status: AuthStatus;
  // null while the users/{uid} doc subscription is loading or status !== "signed-in"
  onboardingCompleted: boolean | null;
}

const AuthContext = createContext<AuthState>({
  user: null,
  status: "loading",
  onboardingCompleted: null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    status: "loading",
    onboardingCompleted: null,
  });

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    try {
      unsubscribe = onAuthStateChanged(getFirebaseAuth(), (user) => {
        setState({
          user,
          status: user ? "signed-in" : "signed-out",
          onboardingCompleted: null,
        });
      });
    } catch (err) {
      console.error("Firebase Auth init failed", err);
      setState({
        user: null,
        status: "signed-out",
        onboardingCompleted: null,
      });
    }
    return () => unsubscribe?.();
  }, []);

  useEffect(() => {
    if (state.status !== "signed-in" || !state.user) return;
    const uid = state.user.uid;
    let unsub: (() => void) | undefined;
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;

    const attach = () => {
      if (cancelled) return;
      try {
        const ref = doc(getFirebaseDb(), "users", uid);
        unsub = onSnapshot(
          ref,
          (snap) => {
            const completed = Boolean(
              snap.exists() && snap.data()?.onboardingCompletedAt,
            );
            setState((prev) =>
              prev.user?.uid === uid
                ? { ...prev, onboardingCompleted: completed }
                : prev,
            );
          },
          (err) => {
            // Firestore destroys the listener on error. On permission-denied
            // during the auth-token bootstrap window, retry with backoff
            // (the fresh ID token usually propagates within a second).
            const code = (err as { code?: string }).code;
            if (code === "permission-denied" && attempt < 3 && !cancelled) {
              attempt += 1;
              const delay = 500 * attempt;
              retryTimer = setTimeout(attach, delay);
              return;
            }
            console.error("Onboarding state subscription failed", err);
          },
        );
      } catch (err) {
        console.error("Onboarding state subscription init failed", err);
      }
    };

    attach();
    return () => {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      unsub?.();
    };
  }, [state.status, state.user]);

  const value = useMemo(() => state, [state]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}

/**
 * Triggers Google sign-in via popup and writes the user's identity doc.
 *
 * On first sign-in, all five identity fields are written. On subsequent
 * sign-ins, `createdAt` is preserved and only the mutable fields are merged.
 * Throws on OAuth error or popup-blocked; the caller decides what to surface.
 */
export async function signInWithGoogle(): Promise<User> {
  const auth = getFirebaseAuth();
  const provider = new GoogleAuthProvider();
  const credential = await signInWithPopup(auth, provider);
  await upsertUserIdentity(credential.user);
  return credential.user;
}

export async function signOutOfShomery(): Promise<void> {
  await firebaseSignOut(getFirebaseAuth());
}

export async function markOnboardingCompleted(uid: string): Promise<void> {
  const ref = doc(getFirebaseDb(), "users", uid);
  await setDoc(ref, { onboardingCompletedAt: serverTimestamp() }, { merge: true });
}

async function upsertUserIdentity(user: User): Promise<void> {
  const db = getFirebaseDb();
  const ref = doc(db, "users", user.uid);
  const snap = await getDoc(ref);
  const now = serverTimestamp();

  const mutable = {
    email: user.email ?? "",
    displayName: user.displayName ?? "",
    photoURL: user.photoURL ?? "",
    lastSignedInAt: now,
  };

  if (snap.exists()) {
    await setDoc(ref, mutable, { merge: true });
  } else {
    await setDoc(ref, { ...mutable, createdAt: now });
  }
}
