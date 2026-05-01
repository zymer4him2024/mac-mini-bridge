"use client";

import type { FolderItem } from "@shomery/shared-types";
import { useLocale, useTranslations } from "next-intl";

import { formatRelativeTime } from "@/lib/intl/relative-time";

import { PdfLink } from "./pdf-link";

export function EmailCard({ item }: { item: FolderItem }) {
  const t = useTranslations("feed");
  const locale = useLocale();

  const created = item.createdAt?.toDate?.() ?? null;
  const relative = created
    ? formatRelativeTime(created, locale)
    : "";

  const urgencyKey = item.urgency;
  const urgencyClass =
    urgencyKey === "high"
      ? "bg-warn/10 text-warn"
      : "bg-soft/10 text-soft";

  return (
    <article className="border-l-accent border-brand bg-paper py-5 pl-5 pr-4 shadow-sm">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-ink">
            {t("senderLine", { from: item.from || t("unknownSender") })}
          </p>
          <p className="mt-0.5 text-sm text-soft">{item.folderSubject}</p>
        </div>
        <span
          className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold ${urgencyClass}`}
        >
          {t(`urgency.${urgencyKey}`)}
        </span>
      </header>

      {item.keyPoints.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-ink">
          {item.keyPoints.slice(0, 5).map((point, idx) => (
            <li key={idx}>{point}</li>
          ))}
        </ul>
      ) : null}

      <footer className="mt-4 flex items-center justify-between gap-3">
        {item.pdfStoragePath && item.pdfFilename ? (
          <PdfLink
            storagePath={item.pdfStoragePath}
            filename={item.pdfFilename}
          />
        ) : (
          <span />
        )}
        {relative ? (
          <time className="text-xs text-soft">{relative}</time>
        ) : null}
      </footer>
    </article>
  );
}
