import type { FolderItem } from "@shomery/shared-types";
import { Timestamp } from "firebase/firestore";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getBlobMock = vi.fn();

vi.mock("firebase/storage", () => ({
  getBlob: (...args: unknown[]) => getBlobMock(...args),
  ref: (_storage: unknown, path: string) => ({ path }),
}));

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseStorage: () => ({}),
}));

import {
  MarkdownDriveNotReadyError,
  MarkdownNotEmittedError,
  getMarkdown,
} from "@/lib/markdown";

function makeItem(overrides: Partial<FolderItem> = {}): FolderItem {
  return {
    uid: "alice",
    folderSubject: "Acme deal",
    folderSlug: "acme-deal",
    date: "2026-04-29",
    from: "Acme <deals@acme.com>",
    urgency: "med",
    keyPoints: [],
    asks: [],
    suggestedResponse: "",
    pdfFilename: "acme.pdf",
    createdAt: Timestamp.fromDate(new Date()),
    ...overrides,
  };
}

describe("getMarkdown", () => {
  beforeEach(() => {
    getBlobMock.mockReset();
  });

  it("throws MarkdownNotEmittedError when markdownStoragePath is missing", async () => {
    await expect(getMarkdown(makeItem())).rejects.toBeInstanceOf(
      MarkdownNotEmittedError,
    );
  });

  it("throws MarkdownDriveNotReadyError for drive:// URIs", async () => {
    await expect(
      getMarkdown(
        makeItem({
          markdownStoragePath: "drive://some-folder-id/some-file.md",
        }),
      ),
    ).rejects.toBeInstanceOf(MarkdownDriveNotReadyError);
  });

  it("downloads the blob and returns the markdown string for storage paths", async () => {
    const blob = {
      text: () => Promise.resolve("# hello\n\nbody"),
    };
    getBlobMock.mockResolvedValue(blob);

    const content = await getMarkdown(
      makeItem({
        markdownStoragePath: "summaries/alice/acme-deal/abc123.md",
      }),
    );

    expect(content).toBe("# hello\n\nbody");
    expect(getBlobMock).toHaveBeenCalledOnce();
    const [refArg] = getBlobMock.mock.calls[0]!;
    expect((refArg as { path: string }).path).toBe(
      "summaries/alice/acme-deal/abc123.md",
    );
  });

  it("propagates errors from the storage SDK", async () => {
    getBlobMock.mockRejectedValue(new Error("storage/object-not-found"));
    await expect(
      getMarkdown(
        makeItem({
          markdownStoragePath: "summaries/alice/acme-deal/abc123.md",
        }),
      ),
    ).rejects.toThrow("storage/object-not-found");
  });
});
