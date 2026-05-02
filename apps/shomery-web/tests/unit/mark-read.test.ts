import { beforeEach, describe, expect, it, vi } from "vitest";

const txGet = vi.fn();
const txUpdate = vi.fn();
const runTransactionMock = vi.fn(async (_db: unknown, fn: (tx: unknown) => Promise<void>) => {
  await fn({ get: txGet, update: txUpdate });
});

vi.mock("firebase/firestore", () => ({
  doc: (_db: unknown, path: string) => ({ path }),
  runTransaction: (db: unknown, fn: (tx: unknown) => Promise<void>) =>
    runTransactionMock(db, fn),
  serverTimestamp: () => "SERVER_TIMESTAMP",
}));

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

import { markItemRead } from "@/lib/mark-read";

const itemPath = "users/alice/folders/acme/items/i1";
const folderPath = "users/alice/folders/acme";

function setupItem(data: Record<string, unknown> | null) {
  txGet.mockImplementationOnce(async (ref: { path: string }) => {
    if (ref.path !== itemPath) throw new Error(`unexpected ref ${ref.path}`);
    if (data === null) return { exists: () => false, data: () => undefined };
    return { exists: () => true, data: () => data };
  });
}

function setupFolder(data: Record<string, unknown> | null) {
  txGet.mockImplementationOnce(async (ref: { path: string }) => {
    if (ref.path !== folderPath) throw new Error(`unexpected ref ${ref.path}`);
    if (data === null) return { exists: () => false, data: () => undefined };
    return { exists: () => true, data: () => data };
  });
}

describe("markItemRead", () => {
  beforeEach(() => {
    txGet.mockReset();
    txUpdate.mockReset();
    runTransactionMock.mockClear();
  });

  it("sets readAt and decrements unreadCount when item is unread and folder has unread > 0", async () => {
    setupItem({});
    setupFolder({ unreadCount: 3 });

    await markItemRead("alice", "acme", "i1");

    expect(txUpdate).toHaveBeenCalledTimes(2);
    expect(txUpdate).toHaveBeenNthCalledWith(
      1,
      { path: itemPath },
      { readAt: "SERVER_TIMESTAMP" },
    );
    expect(txUpdate).toHaveBeenNthCalledWith(
      2,
      { path: folderPath },
      { unreadCount: 2 },
    );
  });

  it("does not decrement when folder.unreadCount is already zero", async () => {
    setupItem({});
    setupFolder({ unreadCount: 0 });

    await markItemRead("alice", "acme", "i1");

    expect(txUpdate).toHaveBeenCalledTimes(1);
    expect(txUpdate).toHaveBeenCalledWith(
      { path: itemPath },
      { readAt: "SERVER_TIMESTAMP" },
    );
  });

  it("treats missing unreadCount as zero (no folder write)", async () => {
    setupItem({});
    setupFolder({});

    await markItemRead("alice", "acme", "i1");

    expect(txUpdate).toHaveBeenCalledTimes(1);
    expect(txUpdate).toHaveBeenCalledWith(
      { path: itemPath },
      { readAt: "SERVER_TIMESTAMP" },
    );
  });

  it("no-ops when item is already read", async () => {
    setupItem({ readAt: "EXISTING" });

    await markItemRead("alice", "acme", "i1");

    expect(txUpdate).not.toHaveBeenCalled();
  });

  it("no-ops when item does not exist", async () => {
    setupItem(null);

    await markItemRead("alice", "acme", "i1");

    expect(txUpdate).not.toHaveBeenCalled();
  });
});
