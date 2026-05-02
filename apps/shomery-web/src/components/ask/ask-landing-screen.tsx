"use client";

import { useTranslations } from "next-intl";

export function AskLandingScreen() {
  const t = useTranslations("askLanding");

  return (
    <main className="mx-auto max-w-2xl px-6 py-8">
      <header className="border-l-accent border-brand bg-brand-tint py-6 pl-5 pr-4">
        <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>
        <p className="mt-2 text-sm text-ink">{t("body")}</p>
      </header>

      <p className="mt-6 text-sm text-soft">{t("hint")}</p>
    </main>
  );
}
