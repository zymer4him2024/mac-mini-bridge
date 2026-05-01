"use client";

import { useEffect, useMemo, useState } from "react";

import type { Folder, Group } from "@shomery/shared-types";
import { collection, limit, orderBy, query } from "firebase/firestore";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/routing";
import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";

const SUBJECTS_LIMIT = 100;
const COLLAPSED_STORAGE_KEY = "shomery.subjectsNav.collapsedGroups";

interface SubjectRow {
  id: string;
  folder: Folder;
}

export function SubjectsNav({ uid }: { uid: string }) {
  const t = useTranslations("subjects");
  const pathname = usePathname();
  const [rows, setRows] = useState<SubjectRow[] | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [collapsed, toggleCollapsed] = useCollapsedSet(COLLAPSED_STORAGE_KEY);

  useEffect(() => {
    const q = query(
      collection(getFirebaseDb(), `users/${uid}/folders`),
      orderBy("updatedAt", "desc"),
      limit(SUBJECTS_LIMIT),
    );
    return subscribeWithRetry(q, (snap) => {
      setRows(
        snap.docs.map((d) => ({ id: d.id, folder: d.data() as Folder })),
      );
    });
  }, [uid]);

  useEffect(() => {
    const q = query(
      collection(getFirebaseDb(), `users/${uid}/groups`),
      orderBy("updatedAt", "desc"),
    );
    return subscribeWithRetry(q, (snap) => {
      setGroups(snap.docs.map((d) => d.data() as Group));
    });
  }, [uid]);

  const tree = useMemo(() => buildTree(rows ?? [], groups), [rows, groups]);

  if (rows === null) {
    return (
      <ul className="space-y-1" aria-label={t("navLoading")}>
        {[0, 1, 2].map((i) => (
          <li key={i} className="h-7 rounded bg-soft/10" aria-hidden="true" />
        ))}
      </ul>
    );
  }

  if (rows.length === 0) {
    return <p className="text-sm text-soft">{t("navEmpty")}</p>;
  }

  return (
    <div className="space-y-3">
      {tree.groups.length > 0 ? (
        <ul className="space-y-0.5">
          {tree.groups.map((g) => {
            const isCollapsed = collapsed.has(g.group.groupId);
            const ariaKey = isCollapsed ? "expandGroup" : "collapseGroup";
            return (
              <li key={g.group.groupId}>
                <button
                  type="button"
                  onClick={() => toggleCollapsed(g.group.groupId)}
                  aria-expanded={!isCollapsed}
                  aria-label={t(ariaKey, { name: g.group.name })}
                  className="flex w-full items-center justify-between rounded px-2 py-1 text-xs font-bold uppercase tracking-wide text-soft hover:bg-soft/5 hover:text-ink"
                >
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden="true">{isCollapsed ? "▸" : "▾"}</span>
                    <span className="truncate normal-case tracking-normal">
                      {g.group.name}
                    </span>
                  </span>
                  <span className="ml-2 shrink-0 text-xs font-normal normal-case tracking-normal text-soft">
                    {t("itemCount", { count: g.members.length })}
                  </span>
                </button>
                {!isCollapsed && g.members.length > 0 ? (
                  <ul className="mt-0.5 space-y-0.5 pl-4">
                    {g.members.map(({ id, folder }) => (
                      <SubjectLink
                        key={id}
                        folder={folder}
                        pathname={pathname}
                        countLabel={t("itemCount", {
                          count: folder.pdfCount,
                        })}
                      />
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {tree.ungrouped.length > 0 ? (
        <ul className="space-y-0.5">
          {tree.groups.length > 0 ? (
            <li>
              <p className="px-2 py-1 text-xs font-bold uppercase tracking-wide text-soft">
                {t("ungroupedHeading")}
              </p>
            </li>
          ) : null}
          {tree.ungrouped.map(({ id, folder }) => (
            <SubjectLink
              key={id}
              folder={folder}
              pathname={pathname}
              countLabel={t("itemCount", { count: folder.pdfCount })}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SubjectLink({
  folder,
  pathname,
  countLabel,
}: {
  folder: Folder;
  pathname: string;
  countLabel: string;
}) {
  const target = `/subjects/${folder.subjectSlug}`;
  const active = pathname === target;
  return (
    <li>
      <Link
        href={target}
        className={`flex items-center justify-between rounded border-l-2 px-3 py-1.5 text-sm transition-colors ${
          active
            ? "border-brand bg-brand-tint text-ink"
            : "border-transparent text-soft hover:bg-soft/5 hover:text-ink"
        }`}
      >
        <span className="truncate font-medium">{folder.subject}</span>
        <span className="ml-2 shrink-0 text-xs text-soft">{countLabel}</span>
      </Link>
    </li>
  );
}

interface BuiltTree {
  groups: { group: Group; members: SubjectRow[] }[];
  ungrouped: SubjectRow[];
}

/**
 * Defensive: a subject might be listed by more than one group (the "subject in
 * one group" invariant is enforced client-side, not by Firestore rules).
 * First-encountered group wins; the rest of the listings are ignored.
 * A group whose `subjectSlugs[]` references a deleted folder slug silently
 * skips the missing entries — we render only members that resolve.
 */
function buildTree(rows: SubjectRow[], groups: Group[]): BuiltTree {
  const folderBySlug = new Map<string, SubjectRow>();
  for (const row of rows) folderBySlug.set(row.folder.subjectSlug, row);

  const claimed = new Set<string>();
  const groupedOut = groups.map((group) => {
    const members: SubjectRow[] = [];
    for (const slug of group.subjectSlugs) {
      if (claimed.has(slug)) continue;
      const row = folderBySlug.get(slug);
      if (!row) continue;
      claimed.add(slug);
      members.push(row);
    }
    return { group, members };
  });

  const ungrouped = rows.filter((row) => !claimed.has(row.folder.subjectSlug));
  return { groups: groupedOut, ungrouped };
}

function useCollapsedSet(
  storageKey: string,
): [Set<string>, (id: string) => void] {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return new Set();
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) return new Set();
      const parsed = JSON.parse(raw);
      return new Set(Array.isArray(parsed) ? parsed : []);
    } catch {
      return new Set();
    }
  });

  const toggle = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        window.localStorage.setItem(
          storageKey,
          JSON.stringify(Array.from(next)),
        );
      } catch {
        // ignore quota / privacy-mode errors
      }
      return next;
    });
  };

  return [collapsed, toggle];
}
