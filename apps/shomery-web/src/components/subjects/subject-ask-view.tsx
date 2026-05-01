"use client";

import { useEffect, useState } from "react";

import type { Folder } from "@shomery/shared-types";
import { doc, onSnapshot } from "firebase/firestore";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/routing";
import { AskPanel } from "@/components/subjects/ask-panel";
import { SourcesPanel } from "@/components/subjects/sources-panel";
import { getFirebaseDb } from "@/lib/firebase/client";
import { useAuth } from "@/lib/firebase/auth";

type FolderState = "loading" | "missing" | Folder;

export function SubjectAskView({ slug }: { slug: string }) {
  const t = useTranslations("subjects.ask");
  const tSubjects = useTranslations("subjects");
  const tFeed = useTranslations("feed");
  const { user, status } = useAuth();
  const [folder, setFolder] = useState<FolderState>("loading");

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const ref = doc(getFirebaseDb(), `users/${user.uid}/folders/${slug}`);
    const unsub = onSnapshot(ref, (snap) => {
      setFolder(snap.exists() ? (snap.data() as Folder) : "missing");
    });
    return unsub;
  }, [status, user, slug]);

  if (folder === "loading") {
    return (
      <main className="mx-auto max-w-5xl px-6 py-8">
        <p className="text-sm text-soft">{tFeed("loading")}</p>
      </main>
    );
  }

  if (folder === "missing") {
    return (
      <main className="mx-auto max-w-5xl px-6 py-8">
        <p className="text-sm text-soft">{tSubjects("detailNotFound")}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <Link
        href={`/subjects/${slug}`}
        className="text-sm text-soft hover:text-ink"
      >
        {t("backToSubject")}
      </Link>

      <header className="mt-3">
        <h1 className="text-2xl font-bold text-ink">
          {t("title", { subject: folder.subject })}
        </h1>
        <p className="mt-1 text-sm text-soft">{t("subtitle")}</p>
      </header>

      <div className="mt-6 flex flex-col gap-8 md:flex-row">
        <SourcesPanel slug={slug} />
        <div className="flex-1">
          <AskPanel slug={slug} subjectDisplay={folder.subject} />
        </div>
      </div>
    </main>
  );
}
