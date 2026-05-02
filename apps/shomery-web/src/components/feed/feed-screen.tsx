"use client";

import { useState } from "react";

import { useTranslations } from "next-intl";

import { useAuth } from "@/lib/firebase/auth";

import { FeedList } from "./feed-list";

export function FeedScreen() {
  const t = useTranslations("feed");
  const { user, status } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);

  if (status !== "signed-in" || !user) {
    return (
      <main className="px-6 py-10">
        <p className="text-sm text-soft">{t("loading")}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>
        {unreadCount > 0 ? (
          <p className="mt-1 text-sm text-soft">
            {t("processedSubtitle", { count: unreadCount })}
          </p>
        ) : null}
      </header>
      <FeedList uid={user.uid} onUnreadCount={setUnreadCount} />
    </main>
  );
}
