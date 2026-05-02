"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/routing";
import {
  useNewItemToasts,
  type NewItemToast,
} from "@/lib/use-new-item-toasts";

export function FeedToastStack({ uid }: { uid: string }) {
  const { toasts, dismiss } = useNewItemToasts(uid);
  const t = useTranslations("feed");

  if (toasts.length === 0) return null;

  return (
    <div
      role="region"
      aria-label={t("toast.regionLabel")}
      aria-live="polite"
      className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2"
    >
      {toasts.map((toast) => (
        <FeedToastCard
          key={toast.id}
          toast={toast}
          onDismiss={() => dismiss(toast.id)}
        />
      ))}
    </div>
  );
}

function FeedToastCard({
  toast,
  onDismiss,
}: {
  toast: NewItemToast;
  onDismiss: () => void;
}) {
  const t = useTranslations("feed");
  const { id, item } = toast;
  const href = item.markdownStoragePath
    ? `/subjects/${item.folderSlug}/items/${id}`
    : `/subjects/${item.folderSlug}`;

  return (
    <div
      role="status"
      className="border-l-accent border-brand pointer-events-auto flex items-start gap-2 bg-paper py-3 pl-3 pr-2 shadow-lg"
    >
      <Link
        href={href}
        onClick={onDismiss}
        className="min-w-0 flex-1 text-left"
      >
        <p className="text-xs font-bold uppercase tracking-wide text-brand">
          {t("toast.newEmailLabel")}
        </p>
        <p className="mt-0.5 truncate text-sm font-bold text-ink">
          {t("senderLine", { from: item.from || t("unknownSender") })}
        </p>
        <p className="mt-0.5 truncate text-sm text-soft">
          {item.folderSubject}
        </p>
      </Link>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={t("toast.dismissLabel")}
        className="rounded-md p-1 text-soft hover:bg-soft/5 hover:text-ink"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
