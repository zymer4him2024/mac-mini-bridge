"use client";

import { useEffect, useRef, useState } from "react";

import type { Group } from "@shomery/shared-types";
import {
  collection,
  deleteDoc,
  doc,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
  updateDoc,
  writeBatch,
} from "firebase/firestore";

import { subscribeWithRetry } from "@/lib/firebase/subscribe";
import { getFirebaseDb } from "@/lib/firebase/client";

export interface UseGroupsResult {
  /** null while the listener is loading; [] when there are no groups. */
  groups: Group[] | null;
  createGroup: (name: string, subjectSlugs?: string[]) => Promise<string>;
  renameGroup: (groupId: string, name: string) => Promise<void>;
  setMembers: (groupId: string, subjectSlugs: string[]) => Promise<void>;
  deleteGroup: (groupId: string) => Promise<void>;
}

const groupsPath = (uid: string) => `users/${uid}/groups`;
const groupDocPath = (uid: string, groupId: string) =>
  `${groupsPath(uid)}/${groupId}`;

export function useGroups(uid: string): UseGroupsResult {
  const [groups, setGroups] = useState<Group[] | null>(null);
  // Mutations need the current groups list to enforce the "subject in zero or
  // one groups" invariant atomically. Reading from React state inside an
  // async callback can go stale between snapshot updates and the mutation
  // firing, so we mirror the latest snapshot into a ref.
  const groupsRef = useRef<Group[]>([]);

  useEffect(() => {
    const q = query(
      collection(getFirebaseDb(), groupsPath(uid)),
      orderBy("updatedAt", "desc"),
    );
    return subscribeWithRetry(q, (snap) => {
      const next = snap.docs.map((d) => d.data() as Group);
      groupsRef.current = next;
      setGroups(next);
    });
  }, [uid]);

  const createGroup = async (
    name: string,
    subjectSlugs: string[] = [],
  ): Promise<string> => {
    const groupId = crypto.randomUUID();
    const ref = doc(getFirebaseDb(), groupDocPath(uid, groupId));
    // setMembers handles cross-group dedupe on edit; on create, we still
    // strip any slugs that another group already owns so we never start
    // out violating the invariant.
    const cleaned = await stripFromOtherGroups(uid, groupId, subjectSlugs);
    await setDoc(ref, {
      groupId,
      name,
      subjectSlugs: cleaned,
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    });
    return groupId;
  };

  const renameGroup = async (groupId: string, name: string): Promise<void> => {
    const ref = doc(getFirebaseDb(), groupDocPath(uid, groupId));
    await updateDoc(ref, { name, updatedAt: serverTimestamp() });
  };

  const setMembers = async (
    groupId: string,
    subjectSlugs: string[],
  ): Promise<void> => {
    const db = getFirebaseDb();
    const batch = writeBatch(db);
    const incoming = new Set(subjectSlugs);
    // Strip every incoming slug from any *other* group that currently
    // contains it, so the invariant "a subject belongs to at most one group"
    // is restored in the same atomic write that adds the slug here.
    for (const other of groupsRef.current) {
      if (other.groupId === groupId) continue;
      const filtered = other.subjectSlugs.filter((slug) => !incoming.has(slug));
      if (filtered.length === other.subjectSlugs.length) continue;
      batch.update(doc(db, groupDocPath(uid, other.groupId)), {
        subjectSlugs: filtered,
        updatedAt: serverTimestamp(),
      });
    }
    batch.update(doc(db, groupDocPath(uid, groupId)), {
      subjectSlugs,
      updatedAt: serverTimestamp(),
    });
    await batch.commit();
  };

  const deleteGroup = async (groupId: string): Promise<void> => {
    await deleteDoc(doc(getFirebaseDb(), groupDocPath(uid, groupId)));
  };

  return { groups, createGroup, renameGroup, setMembers, deleteGroup };
}

async function stripFromOtherGroups(
  uid: string,
  ownGroupId: string,
  subjectSlugs: string[],
): Promise<string[]> {
  if (subjectSlugs.length === 0) return [];
  const db = getFirebaseDb();
  const batch = writeBatch(db);
  // We need to read the existing groups to know which currently own these
  // slugs. The caller is creating, so we may not yet have the new groupId
  // in groupsRef — that's fine because the new doc doesn't exist yet.
  const { getDocs } = await import("firebase/firestore");
  const snap = await getDocs(collection(db, groupsPath(uid)));
  const incoming = new Set(subjectSlugs);
  let touched = false;
  for (const d of snap.docs) {
    if (d.id === ownGroupId) continue;
    const data = d.data() as Group;
    const filtered = data.subjectSlugs.filter((slug) => !incoming.has(slug));
    if (filtered.length === data.subjectSlugs.length) continue;
    batch.update(d.ref, {
      subjectSlugs: filtered,
      updatedAt: serverTimestamp(),
    });
    touched = true;
  }
  if (touched) await batch.commit();
  return subjectSlugs;
}
