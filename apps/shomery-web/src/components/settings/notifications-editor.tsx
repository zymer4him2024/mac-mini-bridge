"use client";

import { useState } from "react";

import { doc, setDoc } from "firebase/firestore";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { getFirebaseDb } from "@/lib/firebase/client";

type SaveState = "idle" | "saving" | "saved" | "error";

export interface NotificationsValue {
  digestEnabled: boolean;
  telegramEnabled: boolean;
  telegramChatId: string;
}

const COMING_SOON_CHANNELS = [
  "kakaoTalk",
  "whatsApp",
  "telegram",
  "sms",
] as const;
type ComingSoonChannel = (typeof COMING_SOON_CHANNELS)[number];

const CHANNEL_DOT_CLASS: Record<ComingSoonChannel | "emailDigest", string> = {
  emailDigest: "bg-soft",
  kakaoTalk: "bg-[#FEE500]",
  whatsApp: "bg-[#25D366]",
  telegram: "bg-[#0088CC]",
  sms: "bg-soft",
};

export function NotificationsEditor({
  uid,
  initial,
}: {
  uid: string;
  initial: NotificationsValue;
}) {
  const t = useTranslations("settings.notifications");
  const tChannels = useTranslations("settings.notifications.channels");
  const [digestEnabled, setDigestEnabled] = useState(initial.digestEnabled);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  const dirty = digestEnabled !== initial.digestEnabled;

  const onSave = async () => {
    setSaveState("saving");
    try {
      await setDoc(
        doc(getFirebaseDb(), `users/${uid}/config/main`),
        { digestEnabled },
        { merge: true },
      );
      setSaveState("saved");
    } catch (err) {
      console.error("Failed to save notification settings", err);
      setSaveState("error");
    }
  };

  const markDirty = () => {
    if (saveState !== "idle") setSaveState("idle");
  };

  return (
    <section
      aria-labelledby="notifications-heading"
      className="border-l-accent border-brand bg-paper py-6 pl-6 pr-4 shadow-sm"
    >
      <h2
        id="notifications-heading"
        className="text-base font-bold text-ink"
      >
        {t("label")}
      </h2>
      <p className="mt-1 text-sm text-soft">{t("helpText")}</p>

      <ul className="mt-4 divide-y divide-soft/10">
        <li className="flex items-start justify-between gap-4 py-3">
          <div className="flex flex-1 items-start gap-3">
            <span
              aria-hidden="true"
              className={`mt-1 inline-block h-2.5 w-2.5 rounded-full ${CHANNEL_DOT_CLASS.emailDigest}`}
            />
            <div className="flex-1">
              <p className="text-sm font-bold text-ink">
                {tChannels("emailDigest.label")}
              </p>
              <p className="mt-0.5 text-xs text-soft">
                {tChannels("emailDigest.helpText")}
              </p>
            </div>
          </div>
          <Switch
            checked={digestEnabled}
            onCheckedChange={(next) => {
              setDigestEnabled(next);
              markDirty();
            }}
            aria-label={t(digestEnabled ? "toggleOff" : "toggleOn", {
              channel: tChannels("emailDigest.label"),
            })}
          />
        </li>

        <ComingSoonRow channel="kakaoTalk" />
        <ComingSoonRow channel="whatsApp" />
        <ComingSoonRow channel="telegram" />
        <ComingSoonRow channel="sms" />
      </ul>

      <footer className="mt-6 flex items-center gap-3">
        <Button
          type="button"
          onClick={onSave}
          disabled={!dirty || saveState === "saving"}
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

function ComingSoonRow({ channel }: { channel: ComingSoonChannel }) {
  const t = useTranslations("settings.notifications");
  const tChannels = useTranslations("settings.notifications.channels");
  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <div className="flex flex-1 items-center gap-3">
        <span
          aria-hidden="true"
          className={`inline-block h-2.5 w-2.5 rounded-full ${CHANNEL_DOT_CLASS[channel]}`}
        />
        <p className="text-sm text-soft">{tChannels(`${channel}.label`)}</p>
        <span className="rounded-full bg-brand-tint px-2 py-0.5 text-xs text-soft">
          {t("comingSoonBadge")}
        </span>
      </div>
      <Switch
        checked={false}
        onCheckedChange={() => undefined}
        disabled
        aria-label={tChannels(`${channel}.label`)}
      />
    </li>
  );
}
