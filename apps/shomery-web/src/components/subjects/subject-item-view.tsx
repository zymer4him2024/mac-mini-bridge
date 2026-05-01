"use client";

import { useEffect, useState } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { doc, onSnapshot } from "firebase/firestore";
import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/routing";
import { MarkdownViewer } from "@/components/feed/markdown-viewer";
import { PdfLink } from "@/components/feed/pdf-link";
import { getFirebaseDb } from "@/lib/firebase/client";
import { useAuth } from "@/lib/firebase/auth";
import { formatRelativeTime } from "@/lib/intl/relative-time";

type ItemState = "loading" | "missing" | FolderItem;

export function SubjectItemView({
  slug,
  itemId,
}: {
  slug: string;
  itemId: string;
}) {
  const t = useTranslations("subjects");
  const tFeed = useTranslations("feed");
  const tMd = useTranslations("markdown");
  const locale = useLocale();
  const { user, status } = useAuth();
  const [item, setItem] = useState<ItemState>("loading");

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const ref = doc(
      getFirebaseDb(),
      `users/${user.uid}/folders/${slug}/items/${itemId}`,
    );
    const unsub = onSnapshot(ref, (snap) => {
      setItem(snap.exists() ? (snap.data() as FolderItem) : "missing");
    });
    return unsub;
  }, [status, user, slug, itemId]);

  if (item === "loading") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-soft">{tFeed("loading")}</p>
      </main>
    );
  }

  if (item === "missing") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-soft">{tMd("notFound")}</p>
      </main>
    );
  }

  const created = item.createdAt?.toDate?.() ?? null;
  const relative = created ? formatRelativeTime(created, locale) : "";

  return (
    <main className="mx-auto max-w-2xl px-6 py-8">
      <Link
        href={`/subjects/${slug}`}
        className="text-sm text-soft hover:text-ink"
      >
        {t("backToSubject")}
      </Link>

      <header className="mt-3 border-l-accent border-brand bg-paper py-4 pl-5 pr-4 shadow-sm">
        <p className="text-sm font-bold text-ink">
          {tFeed("senderLine", { from: item.from || tFeed("unknownSender") })}
        </p>
        <p className="mt-0.5 text-sm text-soft">{item.folderSubject}</p>
        {relative ? (
          <time className="mt-1 block text-xs text-soft">{relative}</time>
        ) : null}
      </header>

      <section className="mt-6">
        <MarkdownViewer item={item} />
      </section>

      {item.pdfStoragePath && item.pdfFilename ? (
        <footer className="mt-6">
          <PdfLink
            storagePath={item.pdfStoragePath}
            filename={item.pdfFilename}
          />
        </footer>
      ) : null}
    </main>
  );
}
