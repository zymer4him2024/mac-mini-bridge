"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/routing";

import { OnboardingShell } from "./onboarding-shell";

export function WelcomeScreen() {
  const t = useTranslations("onboarding.welcome");
  return (
    <OnboardingShell step="welcome">
      <h1 className="text-3xl font-bold leading-tight text-ink">
        {t("headline")}
      </h1>
      <p className="mt-4 text-base text-soft">{t("body")}</p>
      <footer className="mt-10">
        <Link href="/onboarding/connect">
          <Button type="button" className="w-full">
            {t("cta")}
          </Button>
        </Link>
      </footer>
    </OnboardingShell>
  );
}
