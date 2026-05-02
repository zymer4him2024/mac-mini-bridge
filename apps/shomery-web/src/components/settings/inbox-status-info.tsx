"use client";

import { useLocale, useTranslations } from "next-intl";

import { useAuth } from "@/lib/firebase/auth";
import { formatRelativeTime } from "@/lib/intl/relative-time";
import { useLastSummary } from "@/lib/use-last-summary";

export function InboxStatusInfo() {
  const t = useTranslations("settings.inbox");
  const locale = useLocale();
  const { user, gmailEmail } = useAuth();
  const connected = Boolean(gmailEmail);
  const last = useLastSummary(connected ? user?.uid ?? null : null);

  return (
    <section
      aria-labelledby="inbox-status-heading"
      className="border-l-accent border-brand bg-paper py-6 pl-6 pr-4 shadow-sm"
    >
      <h2 id="inbox-status-heading" className="text-base font-bold text-ink">
        {t("label")}
      </h2>
      <p className="mt-1 text-sm text-soft">{t("helpText")}</p>

      {connected ? (
        <>
          <div className="mt-4 space-y-1">
            <p className="text-sm font-bold text-ink">{t("connectedLabel")}</p>
            <p className="text-sm text-soft">
              {t("connectedAs", { email: gmailEmail! })}
            </p>
          </div>
          {last.status !== "loading" ? (
            <div className="mt-4 space-y-1">
              <p className="text-sm font-bold text-ink">
                {t("latestSummaryLabel")}
              </p>
              <p className="text-sm text-soft">
                {last.status === "ok"
                  ? t("latestSummary", {
                      when: formatRelativeTime(last.at, locale),
                    })
                  : t("firstSummaryWaiting")}
              </p>
            </div>
          ) : null}
        </>
      ) : (
        <div className="mt-4 space-y-1">
          <p className="text-sm font-bold text-ink">{t("pendingLabel")}</p>
          <p className="text-sm text-soft">{t("pendingBody")}</p>
        </div>
      )}
    </section>
  );
}
