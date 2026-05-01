"use client";

import { useEffect } from "react";

import { useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/firebase/auth";

export function RootRedirect() {
  const router = useRouter();
  const { status, onboardingCompleted } = useAuth();

  useEffect(() => {
    if (status === "signed-out") {
      router.replace("/sign-in");
      return;
    }
    if (status === "signed-in") {
      if (onboardingCompleted === true) router.replace("/feed");
      else if (onboardingCompleted === false) router.replace("/onboarding");
    }
  }, [status, onboardingCompleted, router]);

  return null;
}
