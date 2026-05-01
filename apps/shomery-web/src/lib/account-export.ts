import type { Folder, FolderItem, UserConfig } from "@shomery/shared-types";
import {
  collection,
  doc,
  getDoc,
  getDocs,
  orderBy,
  query,
} from "firebase/firestore";

import { getFirebaseDb } from "@/lib/firebase/client";

interface ExportedFolder {
  folder: Folder;
  items: FolderItem[];
}

export interface ExportPayload {
  schemaVersion: 1;
  exportedAt: string;
  uid: string;
  user: Record<string, unknown> | null;
  config: Partial<UserConfig> | null;
  folders: ExportedFolder[];
}

export async function buildAccountExport(uid: string): Promise<ExportPayload> {
  const db = getFirebaseDb();

  const [userSnap, configSnap, foldersSnap] = await Promise.all([
    getDoc(doc(db, `users/${uid}`)),
    getDoc(doc(db, `users/${uid}/config/main`)),
    getDocs(
      query(
        collection(db, `users/${uid}/folders`),
        orderBy("updatedAt", "desc"),
      ),
    ),
  ]);

  const folders: ExportedFolder[] = await Promise.all(
    foldersSnap.docs.map(async (folderDoc) => {
      const itemsSnap = await getDocs(
        query(
          collection(db, `users/${uid}/folders/${folderDoc.id}/items`),
          orderBy("createdAt", "desc"),
        ),
      );
      return {
        folder: folderDoc.data() as Folder,
        items: itemsSnap.docs.map((d) => d.data() as FolderItem),
      };
    }),
  );

  return {
    schemaVersion: 1,
    exportedAt: new Date().toISOString(),
    uid,
    user: userSnap.exists() ? userSnap.data() : null,
    config: configSnap.exists()
      ? (configSnap.data() as Partial<UserConfig>)
      : null,
    folders,
  };
}

export function downloadExport(payload: ExportPayload): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `shomery-export-${payload.uid}-${payload.exportedAt.replace(/[:.]/g, "-")}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
