import type { ReactNode } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type SnapshotCallback = (snap: {
  docs: { id: string; data: () => FolderItem }[];
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

vi.mock("@/components/feed/email-card", () => ({
  EmailCard: ({ item }: { item: FolderItem }) => (
    <div data-testid="email-card">{item.from}</div>
  ),
}));

import { FeedList } from "@/components/feed/feed-list";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

function makeItem(from: string): FolderItem {
  return {
    uid: "alice",
    folderSubject: "Acme",
    folderSlug: "acme",
    date: "2026-04-29",
    from,
    urgency: "low",
    keyPoints: [],
    asks: [],
    suggestedResponse: "",
    pdfFilename: "",
    createdAt: Timestamp.fromDate(new Date()),
  };
}

describe("FeedList", () => {
  beforeEach(() => {
    lastCallback = null;
    unsub.mockReset();
  });

  it("renders the loading state before any snapshot arrives", () => {
    render(withIntl(<FeedList uid="alice" />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders the empty state when the snapshot has zero rows", () => {
    render(withIntl(<FeedList uid="alice" />));
    act(() => {
      lastCallback?.({ docs: [] });
    });
    expect(
      screen.getByText("We're watching for your first email."),
    ).toBeInTheDocument();
  });

  it("renders one card per snapshot doc", () => {
    render(withIntl(<FeedList uid="alice" />));
    act(() => {
      lastCallback?.({
        docs: [
          { id: "1", data: () => makeItem("alice@x.com") },
          { id: "2", data: () => makeItem("bob@x.com") },
        ],
      });
    });
    expect(screen.getAllByTestId("email-card")).toHaveLength(2);
  });
});
