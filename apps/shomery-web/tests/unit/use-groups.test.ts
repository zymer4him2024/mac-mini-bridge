import type { Group } from "@shomery/shared-types";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

type SnapshotCallback = (snap: {
  docs: { id: string; data: () => Group }[];
}) => void;

const callbacks: SnapshotCallback[] = [];
const setDocSpy = vi.fn().mockResolvedValue(undefined);
const updateDocSpy = vi.fn().mockResolvedValue(undefined);
const deleteDocSpy = vi.fn().mockResolvedValue(undefined);
const batchUpdateSpy = vi.fn();
const batchCommitSpy = vi.fn().mockResolvedValue(undefined);
const getDocsSpy = vi.fn();

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    collection: (_db: unknown, path: string) => ({ __collection: path }),
    doc: (_db: unknown, path: string) => ({ __doc: path }),
    query: (col: unknown) => col,
    orderBy: () => ({}),
    onSnapshot: (_q: unknown, cb: SnapshotCallback) => {
      callbacks.push(cb);
      return vi.fn();
    },
    setDoc: (...args: unknown[]) => setDocSpy(...args),
    updateDoc: (...args: unknown[]) => updateDocSpy(...args),
    deleteDoc: (...args: unknown[]) => deleteDocSpy(...args),
    writeBatch: () => ({
      update: batchUpdateSpy,
      commit: batchCommitSpy,
    }),
    getDocs: (...args: unknown[]) => getDocsSpy(...args),
    serverTimestamp: () => ({ __serverTimestamp: true }),
  };
});

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

import { useGroups } from "@/lib/use-groups";

function makeGroup(groupId: string, subjectSlugs: string[]): Group {
  return {
    groupId,
    name: groupId,
    subjectSlugs,
    createdAt: { seconds: 0, nanoseconds: 0 } as unknown as Group["createdAt"],
    updatedAt: { seconds: 0, nanoseconds: 0 } as unknown as Group["updatedAt"],
  };
}

function pushGroups(groups: Group[]) {
  callbacks[0]?.({
    docs: groups.map((g) => ({ id: g.groupId, data: () => g })),
  });
}

describe("useGroups", () => {
  beforeEach(() => {
    callbacks.length = 0;
    setDocSpy.mockReset().mockResolvedValue(undefined);
    updateDocSpy.mockReset().mockResolvedValue(undefined);
    deleteDocSpy.mockReset().mockResolvedValue(undefined);
    batchUpdateSpy.mockReset();
    batchCommitSpy.mockReset().mockResolvedValue(undefined);
    getDocsSpy.mockReset().mockResolvedValue({ docs: [] });
  });

  it("starts with groups=null and populates on snapshot", async () => {
    const { result } = renderHook(() => useGroups("alice"));
    expect(result.current.groups).toBeNull();
    act(() => {
      pushGroups([makeGroup("g1", ["acme"])]);
    });
    await waitFor(() => {
      expect(result.current.groups).toHaveLength(1);
    });
    expect(result.current.groups?.[0]?.groupId).toBe("g1");
  });

  it("createGroup writes a new doc with a generated id", async () => {
    const { result } = renderHook(() => useGroups("alice"));
    act(() => {
      pushGroups([]);
    });
    let returned: string | undefined;
    await act(async () => {
      returned = await result.current.createGroup("Acme");
    });
    expect(returned).toBeTruthy();
    expect(setDocSpy).toHaveBeenCalledTimes(1);
    const firstCall = setDocSpy.mock.calls[0]!;
    const [ref, payload] = firstCall;
    expect((ref as { __doc: string }).__doc).toBe(
      `users/alice/groups/${returned}`,
    );
    expect((payload as { name: string; subjectSlugs: string[] }).name).toBe(
      "Acme",
    );
    expect(
      (payload as { subjectSlugs: string[] }).subjectSlugs,
    ).toEqual([]);
  });

  it("renameGroup updates only name and updatedAt", async () => {
    const { result } = renderHook(() => useGroups("alice"));
    act(() => {
      pushGroups([makeGroup("g1", [])]);
    });
    await act(async () => {
      await result.current.renameGroup("g1", "Renamed");
    });
    expect(updateDocSpy).toHaveBeenCalledTimes(1);
    const renameCall = updateDocSpy.mock.calls[0]!;
    const [ref, payload] = renameCall;
    expect((ref as { __doc: string }).__doc).toBe("users/alice/groups/g1");
    expect((payload as { name: string }).name).toBe("Renamed");
  });

  it("setMembers strips incoming slugs from other groups in one batch", async () => {
    const { result } = renderHook(() => useGroups("alice"));
    act(() => {
      pushGroups([
        makeGroup("g1", ["acme"]),
        makeGroup("g2", ["okrs", "stale"]),
      ]);
    });
    await act(async () => {
      await result.current.setMembers("g1", ["acme", "okrs"]);
    });
    expect(batchCommitSpy).toHaveBeenCalledTimes(1);
    expect(batchUpdateSpy).toHaveBeenCalledTimes(2);

    const calls = batchUpdateSpy.mock.calls;
    const stripCall = calls.find(
      ([ref]) => (ref as { __doc: string }).__doc === "users/alice/groups/g2",
    );
    const setCall = calls.find(
      ([ref]) => (ref as { __doc: string }).__doc === "users/alice/groups/g1",
    );
    expect(stripCall?.[1].subjectSlugs).toEqual(["stale"]);
    expect(setCall?.[1].subjectSlugs).toEqual(["acme", "okrs"]);
  });

  it("setMembers does not touch groups whose slugs do not overlap", async () => {
    const { result } = renderHook(() => useGroups("alice"));
    act(() => {
      pushGroups([
        makeGroup("g1", ["acme"]),
        makeGroup("g2", ["unrelated"]),
      ]);
    });
    await act(async () => {
      await result.current.setMembers("g1", ["acme", "okrs"]);
    });
    expect(batchUpdateSpy).toHaveBeenCalledTimes(1);
    const onlyCall = batchUpdateSpy.mock.calls[0]!;
    const [ref] = onlyCall;
    expect((ref as { __doc: string }).__doc).toBe("users/alice/groups/g1");
  });

  it("deleteGroup calls deleteDoc on the right path", async () => {
    const { result } = renderHook(() => useGroups("alice"));
    act(() => {
      pushGroups([makeGroup("g1", [])]);
    });
    await act(async () => {
      await result.current.deleteGroup("g1");
    });
    expect(deleteDocSpy).toHaveBeenCalledTimes(1);
    const deleteCall = deleteDocSpy.mock.calls[0]!;
    const [ref] = deleteCall;
    expect((ref as { __doc: string }).__doc).toBe("users/alice/groups/g1");
  });
});
