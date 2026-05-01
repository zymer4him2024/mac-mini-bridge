"use client";

import { useEffect, type ReactNode } from "react";

import { useTranslations } from "next-intl";

import { AppShell } from "@/components/nav/app-shell";
import { useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/firebase/auth";

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  const t = useTranslations("feed");
  const router = useRouter();
  const { user, status, onboardingCompleted } = useAuth();

  useEffect(() => {
    if (status === "signed-out") {
      router.replace("/sign-in");
      return;
    }
    if (status === "signed-in" && onboardingCompleted === false) {
      router.replace("/onboarding");
    }
  }, [status, onboardingCompleted, router]);

  if (
    status !== "signed-in" ||
    !user ||
    onboardingCompleted !== true
  ) {
    return (
      <main className="px-6 py-10">
        <p className="text-sm text-soft">{t("loading")}</p>
      </main>
    );
  }

  return <AppShell uid={user.uid}>{children}</AppShell>;
}
