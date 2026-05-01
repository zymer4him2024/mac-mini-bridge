import type { ReactNode } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type CollSnapshotCallback = (snap: {
  docs: { id: string; data: () => FolderItem }[];
}) => void;

let collCallback: CollSnapshotCallback | null = null;

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    collection: () => ({}),
    orderBy: () => ({}),
    limit: () => ({}),
    query: () => ({ __kind: "query" }),
    onSnapshot: (_q: unknown, cb: CollSnapshotCallback) => {
      collCallback = cb;
      return vi.fn();
    },
  };
});

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

const useAuthMock = vi.fn();
vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

import { SourcesPanel } from "@/components/subjects/sources-panel";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

function makeItem(from: string, keyPoint = ""): FolderItem {
  return {
    uid: "alice",
    folderSubject: "Acme deal",
    folderSlug: "acme",
    date: "2026-04-29",
    from,
    urgency: "low",
    keyPoints: keyPoint ? [keyPoint] : [],
    asks: [],
    suggestedResponse: "",
    pdfFilename: "",
    createdAt: Timestamp.fromDate(new Date()),
  };
}

describe("SourcesPanel", () => {
  beforeEach(() => {
    collCallback = null;
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
  });

  it("shows a loading state until the items snapshot arrives", () => {
    render(withIntl(<SourcesPanel slug="acme" />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows the empty-state copy when there are no items", () => {
    render(withIntl(<SourcesPanel slug="acme" />));
    act(() => {
      collCallback?.({ docs: [] });
    });
    expect(
      screen.getByText(
        "No items in this subject yet — we need at least one summarized email before we can answer.",
      ),
    ).toBeInTheDocument();
  });

  it("renders one row per item with a disabled checked checkbox", () => {
    render(withIntl(<SourcesPanel slug="acme" />));
    act(() => {
      collCallback?.({
        docs: [
          { id: "1", data: () => makeItem("alice@x.com", "Budget approved") },
          { id: "2", data: () => makeItem("bob@x.com", "Need pricing") },
        ],
      });
    });
    expect(screen.getByText("alice@x.com")).toBeInTheDocument();
    expect(screen.getByText("Budget approved")).toBeInTheDocument();
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(2);
    for (const cb of checkboxes) {
      expect(cb).toBeChecked();
      expect(cb).toBeDisabled();
    }
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("renders the read-only-in-v1 footer note", () => {
    render(withIntl(<SourcesPanel slug="acme" />));
    act(() => {
      collCallback?.({ docs: [] });
    });
    expect(
      screen.getByText(
        "All items in this subject are searched. Per-item exclusion ships in the next update.",
      ),
    ).toBeInTheDocument();
  });
});
