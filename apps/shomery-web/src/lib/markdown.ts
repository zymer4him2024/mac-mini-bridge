import type { FolderItem } from "@shomery/shared-types";
import { getBlob, ref } from "firebase/storage";

import { getFirebaseStorage } from "@/lib/firebase/client";

export class MarkdownNotEmittedError extends Error {
  constructor() {
    super("markdown: item has no markdownStoragePath yet");
    this.name = "MarkdownNotEmittedError";
  }
}

export class MarkdownDriveNotReadyError extends Error {
  constructor() {
    super("markdown: drive:// scheme is not yet supported");
    this.name = "MarkdownDriveNotReadyError";
  }
}

export async function getMarkdown(item: FolderItem): Promise<string> {
  const path = item.markdownStoragePath;
  if (!path) {
    throw new MarkdownNotEmittedError();
  }
  if (path.startsWith("drive://")) {
    throw new MarkdownDriveNotReadyError();
  }
  const blob = await getBlob(ref(getFirebaseStorage(), path));
  return await blob.text();
}
