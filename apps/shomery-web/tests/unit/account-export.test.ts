import { beforeEach, describe, expect, it, vi } from "vitest";

const getDocMock = vi.fn();
const getDocsMock = vi.fn();

vi.mock("firebase/firestore", () => ({
  collection: (_db: unknown, path: string) => ({ path }),
  doc: (_db: unknown, path: string) => ({ path }),
  getDoc: (...args: unknown[]) => getDocMock(...args),
  getDocs: (...args: unknown[]) => getDocsMock(...args),
  orderBy: (field: string, dir: string) => ({ field, dir }),
  query: (q: { path: string }) => q,
}));

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

import { buildAccountExport, downloadExport } from "@/lib/account-export";

function snap(data: unknown): {
  exists: () => boolean;
  data: () => unknown;
} {
  return {
    exists: () => data != null,
    data: () => data,
  };
}

function listSnap(rows: { id: string; data: unknown }[]): {
  docs: { id: string; data: () => unknown }[];
} {
  return {
    docs: rows.map((r) => ({ id: r.id, data: () => r.data })),
  };
}

describe("buildAccountExport", () => {
  beforeEach(() => {
    getDocMock.mockReset();
    getDocsMock.mockReset();
  });

  it("collects identity, config, folders, and items into a single payload", async () => {
    getDocMock.mockImplementation((ref: { path: string }) => {
      if (ref.path === "users/alice") {
        return Promise.resolve(snap({ email: "alice@example.com" }));
      }
      if (ref.path === "users/alice/config/main") {
        return Promise.resolve(snap({ priorityWatchSenders: ["@acme.com"] }));
      }
      return Promise.resolve(snap(null));
    });

    getDocsMock.mockImplementation((q: { path: string }) => {
      if (q.path === "users/alice/folders") {
        return Promise.resolve(
          listSnap([
            { id: "acme", data: { subject: "Acme deal", subjectSlug: "acme" } },
          ]),
        );
      }
      if (q.path === "users/alice/folders/acme/items") {
        return Promise.resolve(
          listSnap([{ id: "i1", data: { from: "ceo@acme.com" } }]),
        );
      }
      return Promise.resolve(listSnap([]));
    });

    const payload = await buildAccountExport("alice");

    expect(payload.schemaVersion).toBe(1);
    expect(payload.uid).toBe("alice");
    expect(payload.user).toEqual({ email: "alice@example.com" });
    expect(payload.config).toEqual({ priorityWatchSenders: ["@acme.com"] });
    expect(payload.folders).toHaveLength(1);
    const first = payload.folders[0]!;
    expect(first.folder).toMatchObject({ subject: "Acme deal" });
    expect(first.items).toHaveLength(1);
    expect(first.items[0]).toMatchObject({ from: "ceo@acme.com" });
  });

  it("returns null user/config when those docs do not exist", async () => {
    getDocMock.mockResolvedValue(snap(null));
    getDocsMock.mockResolvedValue(listSnap([]));

    const payload = await buildAccountExport("ghost");

    expect(payload.user).toBeNull();
    expect(payload.config).toBeNull();
    expect(payload.folders).toEqual([]);
  });
});

describe("downloadExport", () => {
  it("triggers a JSON file download via a temporary anchor", () => {
    const createObjectURL = vi.fn(() => "blob:fake");
    const revokeObjectURL = vi.fn();
    const realCreate = URL.createObjectURL;
    const realRevoke = URL.revokeObjectURL;
    URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as unknown as typeof URL.revokeObjectURL;

    const click = vi.fn();
    const realCreateElement = document.createElement.bind(document);
    const createElementSpy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag: string) => {
        const el = realCreateElement(tag);
        if (tag === "a") {
          (el as HTMLAnchorElement).click = click;
        }
        return el;
      });

    downloadExport({
      schemaVersion: 1,
      exportedAt: "2026-04-30T22:00:00.000Z",
      uid: "alice",
      user: null,
      config: null,
      folders: [],
    });

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledOnce();

    URL.createObjectURL = realCreate;
    URL.revokeObjectURL = realRevoke;
    createElementSpy.mockRestore();
  });
});
