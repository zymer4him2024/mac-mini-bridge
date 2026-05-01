import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import {
  connectAuthEmulator,
  getAuth,
  signInAnonymously,
  type Auth,
} from "firebase/auth";
import {
  connectFirestoreEmulator,
  getFirestore,
  type Firestore,
} from "firebase/firestore";
import {
  connectFunctionsEmulator,
  getFunctions,
  type Functions,
} from "firebase/functions";
import {
  connectStorageEmulator,
  getStorage,
  type FirebaseStorage,
} from "firebase/storage";

declare global {
  interface Window {
    __shomeryE2E?: {
      signInAnonymously: () => Promise<string>;
    };
  }
}

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

let cachedApp: FirebaseApp | null = null;
let cachedAuth: Auth | null = null;
let cachedDb: Firestore | null = null;
let cachedStorage: FirebaseStorage | null = null;
let cachedFunctions: Functions | null = null;
let emulatorsWired = false;

function getFirebaseApp(): FirebaseApp {
  if (cachedApp) return cachedApp;
  cachedApp = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
  return cachedApp;
}

function wireEmulatorsOnce(
  auth: Auth,
  db: Firestore,
  storage: FirebaseStorage,
  functions: Functions,
): void {
  if (emulatorsWired) return;
  if (process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR !== "true") return;
  if (typeof window === "undefined") return;

  connectAuthEmulator(auth, "http://localhost:9099", { disableWarnings: true });
  connectFirestoreEmulator(db, "localhost", 8080);
  connectStorageEmulator(storage, "localhost", 9199);
  connectFunctionsEmulator(functions, "localhost", 5001);
  emulatorsWired = true;
}

export function getFirebaseAuth(): Auth {
  if (!cachedAuth) {
    cachedAuth = getAuth(getFirebaseApp());
    wireEmulatorsOnce(
      cachedAuth,
      getFirebaseDb(),
      getFirebaseStorage(),
      getFirebaseFunctions(),
    );
  }
  return cachedAuth;
}

export function getFirebaseDb(): Firestore {
  if (!cachedDb) {
    cachedDb = getFirestore(getFirebaseApp());
  }
  return cachedDb;
}

export function getFirebaseStorage(): FirebaseStorage {
  if (!cachedStorage) {
    cachedStorage = getStorage(getFirebaseApp());
  }
  return cachedStorage;
}

export function getFirebaseFunctions(): Functions {
  if (!cachedFunctions) {
    cachedFunctions = getFunctions(getFirebaseApp());
  }
  return cachedFunctions;
}

if (
  typeof window !== "undefined" &&
  process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATOR === "true"
) {
  window.__shomeryE2E = {
    signInAnonymously: async () => {
      const credential = await signInAnonymously(getFirebaseAuth());
      return credential.user.uid;
    },
  };
}
