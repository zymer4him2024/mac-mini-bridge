"use client";

import { useEffect, useState } from "react";

import type { FolderItem } from "@shomery/shared-types";
import {
  collectionGroup,
  limit,
  orderBy,
  query,
  where,
} from "firebase/firestore";
import { useTranslations } from "next-intl";

import { getFirebaseDb } from "@/lib/firebase/client";
import { subscribeWithRetry } from "@/lib/firebase/subscribe";

import { EmailCard } from "./email-card";

const FEED_LIMIT = 50;

interface FeedRow {
  id: string;
  item: FolderItem;
}

export function FeedList({ uid }: { uid: string }) {
  const t = useTranslations("feed");
  const [rows, setRows] = useState<FeedRow[] | null>(null);

  useEffect(() => {
    const q = query(
      collectionGroup(getFirebaseDb(), "items"),
      where("uid", "==", uid),
      orderBy("createdAt", "desc"),
      limit(FEED_LIMIT),
    );
    return subscribeWithRetry(q, (snap) => {
      const next = snap.docs.map((d) => ({
        id: d.id,
        item: d.data() as FolderItem,
      }));
      setRows(next);
    });
  }, [uid]);

  if (rows === null) {
    return <p className="text-sm text-soft">{t("loading")}</p>;
  }

  if (rows.length === 0) {
    return (
      <div className="border-l-accent border-brand bg-brand-tint py-6 pl-5 pr-4">
        <p className="text-sm text-ink">{t("empty")}</p>
      </div>
    );
  }

  return (
    <ul className="space-y-4">
      {rows.map(({ id, item }) => (
        <li key={id}>
          <EmailCard item={item} itemId={id} />
        </li>
      ))}
    </ul>
  );
}
