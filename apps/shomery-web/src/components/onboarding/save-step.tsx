"use client";

import { useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/routing";
import { markOnboardingCompleted, useAuth } from "@/lib/firebase/auth";

import { OnboardingShell } from "./onboarding-shell";

type CompletionState = "idle" | "saving" | "error";

export function SaveStep() {
  const t = useTranslations("onboarding.save");
  const { user } = useAuth();
  const router = useRouter();
  const [completion, setCompletion] = useState<CompletionState>("idle");

  const onComplete = async () => {
    if (!user) return;
    setCompletion("saving");
    try {
      await markOnboardingCompleted(user.uid);
      router.push("/feed");
    } catch (err) {
      console.error("Failed to mark onboarding complete", err);
      setCompletion("error");
    }
  };

  return (
    <OnboardingShell step={3}>
      <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>

      <section className="mt-6 space-y-1">
        <p className="text-sm font-bold text-ink">{t("storageLabel")}</p>
        <p className="text-sm text-soft">{t("storage")}</p>
      </section>

      <section className="mt-5 space-y-1">
        <p className="text-sm font-bold text-ink">{t("driveLabel")}</p>
        <p className="text-sm text-soft">{t("drive")}</p>
      </section>

      {completion === "error" ? (
        <p role="alert" className="mt-4 text-sm text-warn">
          {t("completeError")}
        </p>
      ) : null}

      <footer className="mt-10">
        <Button
          type="button"
          onClick={onComplete}
          disabled={!user || completion === "saving"}
          className="w-full"
        >
          {completion === "saving" ? t("ctaPending") : t("cta")}
        </Button>
      </footer>
    </OnboardingShell>
  );
}
