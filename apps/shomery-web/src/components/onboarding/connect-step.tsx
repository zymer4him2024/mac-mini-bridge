"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";

import { OnboardingShell } from "./onboarding-shell";

export function ConnectStep() {
  const t = useTranslations("onboarding.connect");
  return (
    <OnboardingShell step={1}>
      <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-4 text-base text-soft">{t("body")}</p>
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
