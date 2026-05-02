import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

interface FakeDoc {
  id: string;
  data: () => Record<string, unknown>;
}

type SnapshotCallback = (snap: { docs: FakeDoc[] }) => void;

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

import { useNewItemToasts } from "@/lib/use-new-item-toasts";

function makeDoc(id: string, from: string, folderSlug = "acme"): FakeDoc {
  return {
    id,
    data: () => ({
      uid: "alice",
      folderSubject: "Acme",
      folderSlug,
      from,
      keyPoints: [],
      asks: [],
      urgency: "low",
    }),
  };
}

describe("useNewItemToasts", () => {
  beforeEach(() => {
    lastCallback = null;
    unsub.mockReset();
    vi.useFakeTimers();
  });

  it("does not toast on the first snapshot (silent baseline)", () => {
    const { result } = renderHook(() => useNewItemToasts("alice"));
    act(() => {
      lastCallback?.({ docs: [makeDoc("a", "Alice")] });
    });
    expect(result.current.toasts).toEqual([]);
  });

  it("toasts only the new docs on subsequent snapshots", () => {
    const { result } = renderHook(() => useNewItemToasts("alice"));
    act(() => {
      lastCallback?.({ docs: [makeDoc("a", "Alice")] });
    });
    act(() => {
      lastCallback?.({
        docs: [makeDoc("b", "Bob"), makeDoc("a", "Alice")],
      });
    });
    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]?.id).toBe("b");
    expect(result.current.toasts[0]?.item.from).toBe("Bob");
  });

  it("auto-dismisses a toast after the timeout", () => {
    const { result } = renderHook(() => useNewItemToasts("alice"));
    act(() => {
      lastCallback?.({ docs: [makeDoc("a", "Alice")] });
    });
    act(() => {
      lastCallback?.({
        docs: [makeDoc("b", "Bob"), makeDoc("a", "Alice")],
      });
    });
    expect(result.current.toasts).toHaveLength(1);
    act(() => {
      vi.advanceTimersByTime(7000);
    });
    expect(result.current.toasts).toEqual([]);
  });

  it("dismiss() removes a toast immediately", () => {
    const { result } = renderHook(() => useNewItemToasts("alice"));
    act(() => {
      lastCallback?.({ docs: [] });
    });
    act(() => {
      lastCallback?.({ docs: [makeDoc("b", "Bob")] });
    });
    expect(result.current.toasts).toHaveLength(1);
    act(() => {
      result.current.dismiss("b");
    });
    expect(result.current.toasts).toEqual([]);
  });

  it("does not subscribe when uid is null", () => {
    renderHook(() => useNewItemToasts(null));
    expect(lastCallback).toBeNull();
  });

  it("unsubscribes on unmount", () => {
    const { unmount } = renderHook(() => useNewItemToasts("alice"));
    unmount();
    expect(unsub).toHaveBeenCalledTimes(1);
  });
});
