"use client";

import { useState } from "react";

import { doc, setDoc } from "firebase/firestore";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/firebase/auth";
import { getFirebaseDb } from "@/lib/firebase/client";
import { useWatchList } from "@/lib/use-watch-list";

import { OnboardingShell } from "./onboarding-shell";

type SaveState = "idle" | "saving" | "error";

export function WatchStep() {
  const t = useTranslations("onboarding.watch");
  const tEditor = useTranslations("settings.watchedSenders");
  const { user } = useAuth();
  const router = useRouter();
  const list = useWatchList([]);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [submitError, setSubmitError] = useState<"min" | null>(null);

  const onContinue = async () => {
    if (!user) return;
    if (list.entries.length === 0) {
      setSubmitError("min");
      return;
    }
    setSubmitError(null);
    setSaveState("saving");
    try {
      await setDoc(
        doc(getFirebaseDb(), `users/${user.uid}/config/main`),
        { priorityWatchSenders: list.entries },
        { merge: true },
      );
      router.push("/onboarding/save");
    } catch (err) {
      console.error("Failed to save onboarding watch list", err);
      setSaveState("error");
    }
  };

  return (
    <OnboardingShell step={2}>
      <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>
      <p className="mt-4 text-base text-soft">{t("body")}</p>

      {list.entries.length > 0 ? (
        <ul className="mt-6 space-y-1">
          {list.entries.map((value) => (
            <li
              key={value}
              className="flex items-center justify-between rounded border border-soft/10 bg-paper px-3 py-2 text-sm text-ink"
            >
              <span className="truncate">{value}</span>
              <button
                type="button"
                aria-label={tEditor("removeAction", { value })}
                onClick={() => list.remove(value)}
                className="ml-3 shrink-0 text-xs text-soft hover:text-warn"
              >
                {tEditor("removeGlyph")}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-4 flex items-start gap-2">
        <input
          type="text"
          value={list.draft}
          onChange={(e) => {
            list.setDraft(e.target.value);
            if (list.validationError) list.clearValidation();
            if (submitError) setSubmitError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              list.add();
            }
          }}
          placeholder={tEditor("addPlaceholder")}
          aria-label={tEditor("addPlaceholder")}
          className="flex-1 rounded border border-soft/20 bg-paper px-3 py-2 text-sm text-ink placeholder:text-soft focus:border-brand focus:outline-none"
        />
        <Button type="button" onClick={() => list.add()}>
          {tEditor("addAction")}
        </Button>
      </div>

      {list.validationError ? (
        <p role="alert" className="mt-2 text-sm text-warn">
          {tEditor(`validation.${list.validationError}`, {
            value: list.validationValue,
          })}
        </p>
      ) : null}
      {submitError === "min" ? (
        <p role="alert" className="mt-2 text-sm text-warn">
          {t("minRequired")}
        </p>
      ) : null}
      {saveState === "error" ? (
        <p role="alert" className="mt-2 text-sm text-warn">
          {t("saveError")}
        </p>
      ) : null}

      <footer className="mt-10">
        <Button
          type="button"
          onClick={onContinue}
          disabled={!user || saveState === "saving"}
          className="w-full"
        >
          {t("cta")}
        </Button>
      </footer>
    </OnboardingShell>
  );
}
