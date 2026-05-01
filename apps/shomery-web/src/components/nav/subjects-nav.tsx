"use client";

import { useEffect, useState } from "react";

import type { Folder } from "@shomery/shared-types";
import {
  collection,
  limit,
  orderBy,
  query,
} from "firebase/firestore";
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
            className="h-7 rounded bg-soft/10"
            aria-hidden="true"
          />
        ))}
      </ul>
    );
  }

  if (rows.length === 0) {
    return <p className="text-sm text-soft">{t("navEmpty")}</p>;
  }

  return (
    <ul className="space-y-0.5">
      {rows.map(({ id, folder }) => {
        const target = `/subjects/${folder.subjectSlug}`;
        const active = pathname === target;
        return (
          <li key={id}>
            <Link
              href={target}
              className={`flex items-center justify-between rounded border-l-2 px-3 py-1.5 text-sm transition-colors ${
                active
                  ? "border-brand bg-brand-tint text-ink"
                  : "border-transparent text-soft hover:bg-soft/5 hover:text-ink"
              }`}
            >
              <span className="truncate font-medium">{folder.subject}</span>
              <span className="ml-2 shrink-0 text-xs text-soft">
                {t("itemCount", { count: folder.pdfCount })}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
