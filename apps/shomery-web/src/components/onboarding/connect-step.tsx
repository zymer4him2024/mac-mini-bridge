"use client";

import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";
import { useAuth } from "@/lib/firebase/auth";
import { formatRelativeTime } from "@/lib/intl/relative-time";
import { useLastSummary } from "@/lib/use-last-summary";

import { OnboardingShell } from "./onboarding-shell";

export function ConnectStep() {
  const t = useTranslations("onboarding.connect");
  const locale = useLocale();
  const { user, gmailEmail } = useAuth();
  const connected = Boolean(gmailEmail);
  const last = useLastSummary(connected ? user?.uid ?? null : null);

  return (
    <OnboardingShell step={1}>
      <h1 className="text-2xl font-bold text-ink">
        {connected ? t("title") : t("pendingTitle")}
      </h1>
      <p className="mt-4 text-base text-soft">
        {connected ? t("body") : t("pendingBody")}
      </p>
      {connected ? (
        <p
          role="status"
          className="mt-6 rounded-md border-l-4 border-brand bg-brand-tint px-4 py-3 text-sm font-bold text-ink"
        >
          {t("connectedBadge", { email: gmailEmail! })}
        </p>
      ) : null}
      {connected && last.status !== "loading" ? (
        <p className="mt-3 text-sm text-soft">
          {last.status === "ok"
            ? t("latestSummary", {
                when: formatRelativeTime(last.at, locale),
              })
            : t("firstSummaryWaiting")}
        </p>
      ) : null}
      <footer className="mt-10">
        <Link href="/onboarding/watch">
          <Button type="button" className="w-full">
            {t("cta")}
          </Button>
        </Link>
      </footer>
    </OnboardingShell>
  );
}
