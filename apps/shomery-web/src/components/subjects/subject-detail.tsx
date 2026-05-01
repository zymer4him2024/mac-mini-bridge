"use client";

import { useEffect, useState } from "react";

import type { Folder, FolderItem } from "@shomery/shared-types";
import {
  collection,
  doc,
  limit,
  onSnapshot,
  orderBy,
  query,
} from "firebase/firestore";
import { useLocale, useTranslations } from "next-intl";

import { EmailCard } from "@/components/feed/email-card";
import { getFirebaseDb } from "@/lib/firebase/client";
import { formatRelativeTime } from "@/lib/intl/relative-time";
import { useAuth } from "@/lib/firebase/auth";

const ITEMS_LIMIT = 100;

type FolderState = "loading" | "missing" | Folder;

interface ItemRow {
  id: string;
  item: FolderItem;
}

export function SubjectDetail({ slug }: { slug: string }) {
  const t = useTranslations("subjects");
  const tFeed = useTranslations("feed");
  const locale = useLocale();
  const { user, status } = useAuth();
  const [folder, setFolder] = useState<FolderState>("loading");
  const [items, setItems] = useState<ItemRow[] | null>(null);

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const ref = doc(getFirebaseDb(), `users/${user.uid}/folders/${slug}`);
    const unsub = onSnapshot(ref, (snap) => {
      if (snap.exists()) {
        setFolder(snap.data() as Folder);
      } else {
        setFolder("missing");
      }
    });
    return unsub;
  }, [status, user, slug]);

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const q = query(
      collection(
        getFirebaseDb(),
        `users/${user.uid}/folders/${slug}/items`,
      ),
      orderBy("createdAt", "desc"),
      limit(ITEMS_LIMIT),
    );
    const unsub = onSnapshot(q, (snap) => {
      setItems(
        snap.docs.map((d) => ({ id: d.id, item: d.data() as FolderItem })),
      );
    });
    return unsub;
  }, [status, user, slug]);

  if (folder === "loading") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-soft">{tFeed("loading")}</p>
      </main>
    );
  }

  if (folder === "missing") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-soft">{t("detailNotFound")}</p>
      </main>
    );
  }

  const updated = folder.updatedAt?.toDate?.() ?? null;
  const relative = updated ? formatRelativeTime(updated, locale) : "";

  return (
    <main className="mx-auto max-w-2xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink">{folder.subject}</h1>
        <p className="mt-1 text-sm text-soft">
          {t("itemCount", { count: folder.pdfCount })}
          {relative ? ` · ${relative}` : ""}
        </p>
      </header>

      {items === null ? (
        <p className="text-sm text-soft">{tFeed("loading")}</p>
      ) : items.length === 0 ? (
        <div className="border-l-accent border-brand bg-brand-tint py-6 pl-5 pr-4">
          <p className="text-sm text-ink">{t("detailEmpty")}</p>
        </div>
      ) : (
        <ul className="space-y-4">
          {items.map(({ id, item }) => (
            <li key={id}>
              <EmailCard item={item} itemId={id} />
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
