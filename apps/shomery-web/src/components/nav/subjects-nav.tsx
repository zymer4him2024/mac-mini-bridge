"use client";

import { useEffect, useMemo, useState } from "react";

import type { Folder, Group } from "@shomery/shared-types";
import { collection, limit, orderBy, query } from "firebase/firestore";
import { Folder as FolderIcon, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/routing";
import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";
import { useGroups } from "@/lib/use-groups";

const SUBJECTS_LIMIT = 100;
const COLLAPSED_STORAGE_KEY = "shomery.subjectsNav.collapsedGroups";
const DUAL_COUNT_SEPARATOR = " · ";
const COLLAPSE_CARET = "▾";
const EXPAND_CARET = "▸";

interface SubjectRow {
  id: string;
  folder: Folder;
}

export function SubjectsNav({ uid }: { uid: string }) {
  const t = useTranslations("subjects");
  const pathname = usePathname();
  const [rows, setRows] = useState<SubjectRow[] | null>(null);
  const [collapsed, toggleCollapsed] = useCollapsedSet(COLLAPSED_STORAGE_KEY);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

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

  // useGroups runs its own listener internally. It is invoked AFTER the
  // folders effect so the registration order matches the previous shape:
  // callbacks[0] = folders, callbacks[1] = groups (preserves existing tests).
  const { groups, createGroup } = useGroups(uid);

  const tree = useMemo(
    () => buildTree(rows ?? [], groups ?? []),
    [rows, groups],
  );

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      setCreating(false);
      return;
    }
    await createGroup(name, []);
    setNewName("");
    setCreating(false);
  };

  return (
    <div>
      <header className="flex items-center justify-between px-3">
        <p className="text-xs font-bold uppercase tracking-wider text-soft">
          {t("subjectsHeader")}
        </p>
        <button
          type="button"
          onClick={() => setCreating((v) => !v)}
          aria-label={t("newGroupCta")}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-soft hover:bg-soft/5 hover:text-ink"
        >
          <Plus className="h-3 w-3" aria-hidden="true" />
          <span>{t("newGroupShort")}</span>
        </button>
      </header>

      {creating ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleCreate();
          }}
          className="mt-2 flex gap-2 px-3"
        >
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder={t("newGroupPlaceholder")}
            aria-label={t("newGroupPlaceholder")}
            maxLength={50}
            className="flex-1 rounded border border-soft/20 bg-paper px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none"
          />
          <button
            type="submit"
            disabled={!newName.trim()}
            className="rounded bg-brand px-2 py-1 text-xs font-bold text-paper hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("newGroupSubmit")}
          </button>
        </form>
      ) : null}

      <div className="mt-2">
        {rows === null ? (
          <ul className="space-y-1" aria-label={t("navLoading")}>
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="h-7 rounded bg-soft/10"
                aria-hidden="true"
              />
            ))}
          </ul>
        ) : rows.length === 0 ? (
          <div className="flex items-start gap-2 rounded-md px-3 py-2 text-sm text-soft">
            <FolderIcon
              className="mt-0.5 h-4 w-4 shrink-0"
              aria-hidden="true"
            />
            <p className="leading-snug">{t("navEmpty")}</p>
          </div>
        ) : (
          <SubjectsTree
            tree={tree}
            pathname={pathname}
            collapsed={collapsed}
            toggleCollapsed={toggleCollapsed}
          />
        )}
      </div>
    </div>
  );
}

function SubjectsTree({
  tree,
  pathname,
  collapsed,
  toggleCollapsed,
}: {
  tree: BuiltTree;
  pathname: string;
  collapsed: Set<string>;
  toggleCollapsed: (id: string) => void;
}) {
  const t = useTranslations("subjects");

  return (
    <div className="space-y-3">
      {tree.groups.length > 0 ? (
        <ul className="space-y-0.5">
          {tree.groups.map((g) => {
            const isCollapsed = collapsed.has(g.group.groupId);
            const ariaKey = isCollapsed ? "expandGroup" : "collapseGroup";
            const groupTotal = g.members.reduce(
              (sum, m) => sum + (m.folder.pdfCount ?? 0),
              0,
            );
            const groupUnread = g.members.reduce(
              (sum, m) => sum + (m.folder.unreadCount ?? 0),
              0,
            );
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
                    <span aria-hidden="true">
                      {isCollapsed ? EXPAND_CARET : COLLAPSE_CARET}
                    </span>
                    <span className="truncate normal-case tracking-normal">
                      {g.group.name}
                    </span>
                  </span>
                  <DualCount
                    total={groupTotal}
                    unread={groupUnread}
                    aria-hidden="true"
                  />
                </button>
                {!isCollapsed && g.members.length > 0 ? (
                  <ul className="mt-0.5 space-y-0.5 pl-4">
                    {g.members.map(({ id, folder }) => (
                      <SubjectLink
                        key={id}
                        folder={folder}
                        pathname={pathname}
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
            <SubjectLink key={id} folder={folder} pathname={pathname} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SubjectLink({
  folder,
  pathname,
}: {
  folder: Folder;
  pathname: string;
}) {
  const t = useTranslations("subjects");
  const target = `/subjects/${folder.subjectSlug}`;
  const active = pathname === target;
  const total = folder.pdfCount ?? 0;
  const unread = folder.unreadCount ?? 0;
  const a11yLabel =
    unread > 0
      ? t("itemCountWithUnread", { count: total, unread })
      : t("itemCount", { count: total });
  return (
    <li>
      <Link
        href={target}
        aria-label={`${folder.subject}, ${a11yLabel}`}
        className={`flex items-center justify-between rounded border-l-2 px-3 py-1.5 text-sm transition-colors ${
          active
            ? "border-brand bg-brand-tint text-ink"
            : "border-transparent text-soft hover:bg-soft/5 hover:text-ink"
        }`}
      >
        <span className="truncate font-medium">{folder.subject}</span>
        <DualCount total={total} unread={unread} aria-hidden="true" />
      </Link>
    </li>
  );
}

/**
 * Dual count `total · unread`, with the unread number in brand emerald when
 * positive. When unread is zero, the dot and unread number are omitted —
 * leaving a single muted total. Aria is set on the parent link so the
 * counts read as one phrase to a screen reader instead of two stray numbers.
 */
function DualCount({
  total,
  unread,
  ...rest
}: {
  total: number;
  unread: number;
  "aria-hidden"?: boolean | "true" | "false";
}) {
  return (
    <span className="ml-2 shrink-0 text-xs font-normal normal-case tracking-normal" {...rest}>
      <span className="text-soft">{total}</span>
      {unread > 0 ? (
        <>
          <span className="text-soft" aria-hidden="true">
            {DUAL_COUNT_SEPARATOR}
          </span>
          <span className="font-bold text-brand">{unread}</span>
        </>
      ) : null}
    </span>
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
