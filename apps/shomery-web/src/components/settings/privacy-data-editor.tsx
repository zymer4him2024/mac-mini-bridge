"use client";

import { useState } from "react";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useRouter } from "@/i18n/routing";
import { callDeleteAccount } from "@/lib/account-delete";
import {
  buildAccountExport,
  downloadExport,
} from "@/lib/account-export";
import { signOutOfShomery } from "@/lib/firebase/auth";

type ExportState = "idle" | "exporting" | "exported" | "error";
type DeleteState = "idle" | "confirming" | "deleting" | "error";

export function PrivacyDataEditor({ uid }: { uid: string }) {
  const t = useTranslations("settings.privacy");
  const router = useRouter();

  const [exportState, setExportState] = useState<ExportState>("idle");
  const [deleteState, setDeleteState] = useState<DeleteState>("idle");
  const [confirmText, setConfirmText] = useState("");

  const onExport = async () => {
    setExportState("exporting");
    try {
      const payload = await buildAccountExport(uid);
      downloadExport(payload);
      setExportState("exported");
    } catch (err) {
      console.error("Failed to build account export", err);
      setExportState("error");
    }
  };

  const onDeleteClick = () => {
    setDeleteState("confirming");
    setConfirmText("");
  };

  const onCancelDelete = () => {
    setDeleteState("idle");
    setConfirmText("");
  };

  const confirmPhrase = t("delete.confirmPhrase");
  const canConfirmDelete = confirmText.trim() === confirmPhrase;

  const onConfirmDelete = async () => {
    if (!canConfirmDelete) return;
    setDeleteState("deleting");
    try {
      await callDeleteAccount();
      // The auth user no longer exists; force sign-out locally and route home.
      await signOutOfShomery();
      router.replace("/sign-in");
    } catch (err) {
      console.error("Failed to delete account", err);
      setDeleteState("error");
    }
  };

  return (
    <section
      aria-labelledby="privacy-data-heading"
      className="border-l-accent border-brand bg-paper py-6 pl-6 pr-4 shadow-sm"
    >
      <h2 id="privacy-data-heading" className="text-base font-bold text-ink">
        {t("label")}
      </h2>
      <p className="mt-1 text-sm text-soft">{t("helpText")}</p>

      <div className="mt-6 space-y-6">
        <div>
          <h3 className="text-sm font-bold text-ink">{t("export.title")}</h3>
          <p className="mt-1 text-sm text-soft">{t("export.body")}</p>
          <div className="mt-3 flex items-center gap-3">
            <Button
              type="button"
              onClick={onExport}
              disabled={exportState === "exporting"}
            >
              {exportState === "exporting"
                ? t("export.actionPending")
                : t("export.action")}
            </Button>
            {exportState === "exported" ? (
              <span className="text-sm text-soft">{t("export.done")}</span>
            ) : null}
            {exportState === "error" ? (
              <span role="alert" className="text-sm text-warn">
                {t("export.error")}
              </span>
            ) : null}
          </div>
        </div>

        <div>
          <h3 className="text-sm font-bold text-ink">{t("delete.title")}</h3>
          <p className="mt-1 text-sm text-soft">{t("delete.body")}</p>

          {deleteState === "idle" || deleteState === "error" ? (
            <div className="mt-3 flex items-center gap-3">
              <Button
                type="button"
                variant="destructive"
                onClick={onDeleteClick}
              >
                {t("delete.action")}
              </Button>
              {deleteState === "error" ? (
                <span role="alert" className="text-sm text-warn">
                  {t("delete.error")}
                </span>
              ) : null}
            </div>
          ) : (
            <div className="mt-3 rounded border border-warn/30 bg-warn/5 p-4">
              <p className="text-sm text-ink">
                {t("delete.confirmPrompt", { phrase: confirmPhrase })}
              </p>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                aria-label={t("delete.confirmInputLabel")}
                placeholder={confirmPhrase}
                className="mt-3 w-full rounded border border-soft/20 bg-paper px-3 py-2 text-sm text-ink placeholder:text-soft focus:border-warn focus:outline-none"
                disabled={deleteState === "deleting"}
              />
              <div className="mt-3 flex items-center gap-3">
                <Button
                  type="button"
                  variant="destructive"
                  onClick={onConfirmDelete}
                  disabled={!canConfirmDelete || deleteState === "deleting"}
                >
                  {deleteState === "deleting"
                    ? t("delete.confirmPending")
                    : t("delete.confirmAction")}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={onCancelDelete}
                  disabled={deleteState === "deleting"}
                >
                  {t("delete.cancel")}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
