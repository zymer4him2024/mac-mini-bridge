"use client";

import { useEffect, useState } from "react";

import { FirebaseError } from "firebase/app";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/routing";
import { signInWithGoogle, useAuth } from "@/lib/firebase/auth";

const SILENT_AUTH_ERRORS = new Set([
  "auth/popup-closed-by-user",
  "auth/cancelled-popup-request",
  "auth/user-cancelled",
]);

export function SignInScreen() {
  const t = useTranslations("signIn");
  const router = useRouter();
  const { status } = useAuth();
  const [pending, setPending] = useState(false);
  const [errorVisible, setErrorVisible] = useState(false);

  useEffect(() => {
    if (status === "signed-in") {
      router.replace("/feed");
    }
  }, [status, router]);

  const onSignIn = async () => {
    setPending(true);
    setErrorVisible(false);
    try {
      await signInWithGoogle();
    } catch (err) {
      if (err instanceof FirebaseError && SILENT_AUTH_ERRORS.has(err.code)) {
        return;
      }
      setErrorVisible(true);
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <section className="w-full max-w-md border-l-accent border-brand bg-paper py-10 pl-6 pr-2">
        <h1 className="text-3xl font-bold leading-tight text-ink">
          {t("headline")}
        </h1>
        <p className="mt-3 text-soft">{t("subhead")}</p>

        <div className="mt-8">
          <Button
            size="lg"
            className="w-full"
            type="button"
            onClick={onSignIn}
            disabled={pending || status === "signed-in"}
          >
            {pending ? t("googleButtonPending") : t("googleButton")}
          </Button>
          {errorVisible ? (
            <p
              role="alert"
              className="mt-3 text-sm text-warn"
            >
              {t("errorTryAgain")}
            </p>
          ) : null}
        </div>

        <p className="mt-6 text-sm text-soft">{t("microcopy")}</p>
      </section>
    </main>
  );
}
