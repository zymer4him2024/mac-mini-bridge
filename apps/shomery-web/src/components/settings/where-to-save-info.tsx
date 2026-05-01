"use client";

import { useTranslations } from "next-intl";

export function WhereToSaveInfo() {
  const t = useTranslations("settings.whereToSave");

  return (
    <section
      aria-labelledby="where-to-save-heading"
      className="border-l-accent border-brand bg-paper py-6 pl-6 pr-4 shadow-sm"
    >
      <h2
        id="where-to-save-heading"
        className="text-base font-bold text-ink"
      >
        {t("label")}
      </h2>
      <p className="mt-1 text-sm text-soft">{t("helpText")}</p>

      <div className="mt-4 space-y-1">
        <p className="text-sm font-bold text-ink">{t("storageLabel")}</p>
        <p className="text-sm text-soft">{t("storage")}</p>
      </div>

      <div className="mt-4 space-y-1">
        <p className="text-sm font-bold text-ink">{t("pathLabel")}</p>
        <code className="block rounded bg-brand-tint px-3 py-2 font-mono text-xs text-ink">
          {t("pathTemplate")}
        </code>
      </div>

      <div className="mt-4 space-y-1">
        <p className="text-sm font-bold text-ink">{t("driveLabel")}</p>
        <p className="text-sm text-soft">{t("drive")}</p>
      </div>
    </section>
  );
}
