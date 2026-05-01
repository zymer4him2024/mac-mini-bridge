"use client";

import { useEffect, useState } from "react";

import { getDownloadURL, ref } from "firebase/storage";
import { useTranslations } from "next-intl";

import { getFirebaseStorage } from "@/lib/firebase/client";

export function PdfLink({
  storagePath,
  filename,
}: {
  storagePath: string;
  filename: string;
}) {
  const t = useTranslations("feed.pdf");
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDownloadURL(ref(getFirebaseStorage(), storagePath))
      .then((value) => {
        if (!cancelled) setUrl(value);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [storagePath]);

  if (!url) {
    return (
      <span className="text-sm text-soft" aria-busy="true">
        {t("pendingLabel", { filename })}
      </span>
    );
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-sm text-ink hover:text-brand-hover"
      aria-label={t("openLabelFor", { filename })}
    >
      {t("linkLabel", { filename })}
    </a>
  );
}
