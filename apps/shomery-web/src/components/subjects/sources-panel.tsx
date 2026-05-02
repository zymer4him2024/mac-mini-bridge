"use client";

import { useEffect, useState } from "react";

import type { FolderItem } from "@shomery/shared-types";
import {
  collection,
  limit,
  onSnapshot,
  orderBy,
  query,
} from "firebase/firestore";
import { useTranslations } from "next-intl";

import { getFirebaseDb } from "@/lib/firebase/client";
import { useAuth } from "@/lib/firebase/auth";

const SOURCES_LIMIT = 50;

interface SourceRow {
  id: string;
  item: FolderItem;
}

export function SourcesPanel({ slug }: { slug: string }) {
  const t = useTranslations("subjects.ask");
  const tFeed = useTranslations("feed");
  const { user, status } = useAuth();
  const [items, setItems] = useState<SourceRow[] | null>(null);

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const q = query(
      collection(
        getFirebaseDb(),
        `users/${user.uid}/folders/${slug}/items`,
      ),
      orderBy("createdAt", "desc"),
      limit(SOURCES_LIMIT),
    );
    const unsub = onSnapshot(q, (snap) => {
      setItems(
        snap.docs.map((d) => ({ id: d.id, item: d.data() as FolderItem })),
      );
    });
    return unsub;
  }, [status, user, slug]);

  return (
    <aside className="w-full md:w-80 md:shrink-0">
      <header className="flex items-baseline justify-between border-b border-gray-200 pb-2">
        <h2 className="text-sm font-bold text-ink">{t("sourcesHeader")}</h2>
        {items !== null ? (
          <span className="text-xs text-soft">
            {t("sourcesItemCount", { count: items.length })}
          </span>
        ) : null}
      </header>

      {items === null ? (
        <p className="mt-3 text-sm text-soft">{tFeed("loading")}</p>
      ) : items.length === 0 ? (
        <p className="mt-3 text-sm text-soft">{t("sourcesEmpty")}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map(({ id, item }) => (
            <li
              key={id}
              className="flex items-start gap-2 rounded border border-gray-100 bg-paper px-3 py-2"
            >
              <input
                type="checkbox"
                checked
                disabled
                aria-label={item.from || tFeed("unknownSender")}
                className="mt-1 h-3.5 w-3.5 cursor-not-allowed accent-brand"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-bold text-ink">
                  {item.from || tFeed("unknownSender")}
                </p>
                <p className="line-clamp-2 text-xs text-soft">
                  {item.keyPoints?.[0] ?? ""}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 text-xs text-soft">{t("sourcesNote")}</p>
    </aside>
  );
}
