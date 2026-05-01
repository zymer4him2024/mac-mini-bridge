"use client";

import { useState } from "react";

import { doc, setDoc } from "firebase/firestore";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { getFirebaseDb } from "@/lib/firebase/client";
import { useWatchList } from "@/lib/use-watch-list";

type SaveState = "idle" | "saving" | "saved" | "error";

export function WatchedSendersEditor({
  uid,
  initial,
}: {
  uid: string;
  initial: string[];
}) {
  const t = useTranslations("settings.watchedSenders");
  const list = useWatchList(initial);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  const onAdd = () => {
    if (list.add()) setSaveState("idle");
  };

  const onRemove = (value: string) => {
    list.remove(value);
    setSaveState("idle");
  };

  const onSave = async () => {
    setSaveState("saving");
    try {
      await setDoc(
        doc(getFirebaseDb(), `users/${uid}/config/main`),
        { priorityWatchSenders: list.entries },
        { merge: true },
      );
      setSaveState("saved");
    } catch (err) {
      console.error("Failed to save watched senders", err);
      setSaveState("error");
    }
  };

  return (
    <section
      aria-labelledby="watched-senders-heading"
      className="border-l-accent border-brand bg-paper py-6 pl-6 pr-4 shadow-sm"
    >
      <h2
        id="watched-senders-heading"
        className="text-base font-bold text-ink"
      >
        {t("label")}
      </h2>
      <p className="mt-1 text-sm text-soft">{t("helpText")}</p>

      {list.entries.length === 0 ? (
        <p className="mt-4 text-sm text-soft">{t("empty")}</p>
      ) : (
        <ul className="mt-4 space-y-1">
          {list.entries.map((value) => (
            <li
              key={value}
              className="flex items-center justify-between rounded border border-soft/10 bg-paper px-3 py-2 text-sm text-ink"
            >
              <span className="truncate">{value}</span>
              <button
                type="button"
                aria-label={t("removeAction", { value })}
                onClick={() => onRemove(value)}
                className="ml-3 shrink-0 text-xs text-soft hover:text-warn"
              >
                {t("removeGlyph")}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex items-start gap-2">
        <input
          type="text"
          value={list.draft}
          onChange={(e) => {
            list.setDraft(e.target.value);
            if (list.validationError) list.clearValidation();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onAdd();
            }
          }}
          placeholder={t("addPlaceholder")}
          aria-label={t("addPlaceholder")}
          className="flex-1 rounded border border-soft/20 bg-paper px-3 py-2 text-sm text-ink placeholder:text-soft focus:border-brand focus:outline-none"
        />
        <Button type="button" onClick={onAdd}>
          {t("addAction")}
        </Button>
      </div>

      {list.validationError ? (
        <p role="alert" className="mt-2 text-sm text-warn">
          {t(`validation.${list.validationError}`, {
            value: list.validationValue,
          })}
        </p>
      ) : null}

      <footer className="mt-6 flex items-center gap-3">
        <Button
          type="button"
          onClick={onSave}
          disabled={!list.dirty || saveState === "saving"}
        >
          {saveState === "saving" ? t("savingAction") : t("saveAction")}
        </Button>
        {saveState === "saved" ? (
          <span className="text-sm text-soft">{t("saved")}</span>
        ) : null}
        {saveState === "error" ? (
          <span role="alert" className="text-sm text-warn">
            {t("saveError")}
          </span>
        ) : null}
      </footer>
    </section>
  );
}
