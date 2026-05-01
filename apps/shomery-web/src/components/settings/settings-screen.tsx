"use client";

import { useEffect, useState } from "react";

import type { Folder, UserConfig } from "@shomery/shared-types";
import {
  collection,
  doc,
  limit,
  onSnapshot,
  orderBy,
  query,
} from "firebase/firestore";
import { useTranslations } from "next-intl";

import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";
import { useAuth } from "@/lib/firebase/auth";

import { GroupsEditor } from "./groups-editor";
import {
  NotificationsEditor,
  type NotificationsValue,
} from "./notifications-editor";
import { PrivacyDataEditor } from "./privacy-data-editor";
import { WatchedSendersEditor } from "./watched-senders-editor";

const FOLDERS_LIMIT = 100;

type ConfigState = "loading" | "ready";

const DEFAULT_NOTIFICATIONS: NotificationsValue = {
  digestEnabled: true,
  telegramEnabled: false,
  telegramChatId: "",
};

export function SettingsScreen() {
  const t = useTranslations("settings");
  const { user, status } = useAuth();
  const [configState, setConfigState] = useState<ConfigState>("loading");
  const [watched, setWatched] = useState<string[]>([]);
  const [notifications, setNotifications] = useState<NotificationsValue>(
    DEFAULT_NOTIFICATIONS,
  );
  const [folders, setFolders] = useState<Folder[]>([]);

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const q = query(
      collection(getFirebaseDb(), `users/${user.uid}/folders`),
      orderBy("updatedAt", "desc"),
      limit(FOLDERS_LIMIT),
    );
    return subscribeWithRetry(q, (snap) => {
      setFolders(snap.docs.map((d) => d.data() as Folder));
    });
  }, [status, user]);

  useEffect(() => {
    if (status !== "signed-in" || !user) return;
    const ref = doc(getFirebaseDb(), `users/${user.uid}/config/main`);
    const unsub = onSnapshot(ref, (snap) => {
      if (snap.exists()) {
        const data = snap.data() as Partial<UserConfig>;
        setWatched(
          Array.isArray(data.priorityWatchSenders)
            ? data.priorityWatchSenders
            : [],
        );
        setNotifications({
          digestEnabled:
            typeof data.digestEnabled === "boolean" ? data.digestEnabled : true,
          telegramEnabled:
            typeof data.telegramEnabled === "boolean"
              ? data.telegramEnabled
              : false,
          telegramChatId:
            typeof data.telegramChatId === "string" ? data.telegramChatId : "",
        });
      } else {
        setWatched([]);
        setNotifications(DEFAULT_NOTIFICATIONS);
      }
      setConfigState("ready");
    });
    return unsub;
  }, [status, user]);

  if (status !== "signed-in" || !user || configState === "loading") {
    return (
      <main className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-soft">{t("loading")}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink">{t("title")}</h1>
      </header>

      <div className="space-y-6">
        <WatchedSendersEditor uid={user.uid} initial={watched} />
        <NotificationsEditor uid={user.uid} initial={notifications} />
        <GroupsEditor uid={user.uid} folders={folders} />
        <PrivacyDataEditor uid={user.uid} />
      </div>
    </main>
  );
}
