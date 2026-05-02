"use client";

import { useEffect, useState } from "react";

import type { Folder } from "@shomery/shared-types";
import {
  collection,
  limit,
  orderBy,
  query,
} from "firebase/firestore";
import { Folder as FolderIcon, FolderOpen } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/routing";
import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";

const SUBJECTS_LIMIT = 100;

interface SubjectRow {
  id: string;
  folder: Folder;
}

export function SubjectsNav({ uid }: { uid: string }) {
  const t = useTranslations("subjects");
  const pathname = usePathname();
  const [rows, setRows] = useState<SubjectRow[] | null>(null);

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

  if (rows === null) {
    return (
      <ul className="space-y-1" aria-label={t("navLoading")}>
        {[0, 1, 2].map((i) => (
          <li
            key={i}
            className="h-8 rounded bg-soft/10"
            aria-hidden="true"
          />
        ))}
      </ul>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex items-start gap-2 rounded-md px-3 py-2 text-sm text-soft">
        <FolderIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <p className="leading-snug">{t("navEmpty")}</p>
      </div>
    );
  }

  return (
    <ul className="space-y-0.5">
      {rows.map(({ id, folder }) => {
        const target = `/subjects/${folder.subjectSlug}`;
        const active = pathname === target;
        const Icon = active ? FolderOpen : FolderIcon;
        return (
          <li key={id}>
            <Link
              href={target}
              className={`flex items-center gap-3 rounded-md border-l-2 px-3 py-1.5 text-sm transition-colors ${
                active
                  ? "border-brand bg-brand-tint text-ink"
                  : "border-transparent text-soft hover:bg-soft/5 hover:text-ink"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate font-medium">
                {folder.subject}
              </span>
              <span className="shrink-0 text-xs text-soft">
                {t("itemCount", { count: folder.pdfCount })}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
