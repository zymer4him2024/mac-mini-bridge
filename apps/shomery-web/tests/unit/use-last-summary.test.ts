import { act, renderHook } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { beforeEach, describe, expect, it, vi } from "vitest";

type SnapshotCallback = (snap: {
  empty: boolean;
  docs: { data: () => { createdAt?: Timestamp } }[];
}) => void;

let lastCallback: SnapshotCallback | null = null;
const unsub = vi.fn();

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    collectionGroup: () => ({}),
    where: () => ({}),
    orderBy: () => ({}),
    limit: () => ({}),
    query: () => ({}),
    onSnapshot: (_q: unknown, cb: SnapshotCallback) => {
      lastCallback = cb;
      return unsub;
    },
  };
});

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

import { useLastSummary } from "@/lib/use-last-summary";

describe("useLastSummary", () => {
  beforeEach(() => {
    lastCallback = null;
    unsub.mockReset();
  });

  it("returns loading and does not subscribe when uid is null", () => {
    const { result } = renderHook(() => useLastSummary(null));
    expect(result.current).toEqual({ status: "loading" });
    expect(lastCallback).toBeNull();
  });

  it("returns 'none' when the snapshot is empty", () => {
    const { result } = renderHook(() => useLastSummary("alice"));
    act(() => {
      lastCallback?.({ empty: true, docs: [] });
    });
    expect(result.current).toEqual({ status: "none" });
  });

  it("returns 'ok' with the createdAt date of the first doc", () => {
    const target = new Date("2026-04-30T12:00:00Z");
    const { result } = renderHook(() => useLastSummary("alice"));
    act(() => {
      lastCallback?.({
        empty: false,
        docs: [{ data: () => ({ createdAt: Timestamp.fromDate(target) }) }],
      });
    });
    expect(result.current.status).toBe("ok");
    if (result.current.status === "ok") {
      expect(result.current.at.getTime()).toBe(target.getTime());
    }
  });

  it("returns 'none' when the doc is missing a createdAt", () => {
    const { result } = renderHook(() => useLastSummary("alice"));
    act(() => {
      lastCallback?.({ empty: false, docs: [{ data: () => ({}) }] });
    });
    expect(result.current).toEqual({ status: "none" });
  });

  it("unsubscribes on unmount", () => {
    const { unmount } = renderHook(() => useLastSummary("alice"));
    unmount();
    expect(unsub).toHaveBeenCalledTimes(1);
  });
});
