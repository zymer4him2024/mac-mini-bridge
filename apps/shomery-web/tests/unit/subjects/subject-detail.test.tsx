import type { ReactNode } from "react";

import type { Folder, FolderItem } from "@shomery/shared-types";
import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type DocSnapshotCallback = (snap: {
  exists: () => boolean;
  data: () => Folder;
}) => void;

type CollSnapshotCallback = (snap: {
  docs: { id: string; data: () => FolderItem }[];
}) => void;

let docCallback: DocSnapshotCallback | null = null;
let collCallback: CollSnapshotCallback | null = null;

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    collection: () => ({}),
    doc: () => ({ __kind: "doc" }),
    orderBy: () => ({}),
    limit: () => ({}),
    query: () => ({ __kind: "query" }),
    onSnapshot: (
      ref: { __kind?: string },
      cb: DocSnapshotCallback | CollSnapshotCallback,
    ) => {
      if (ref?.__kind === "doc") {
        docCallback = cb as DocSnapshotCallback;
      } else {
        collCallback = cb as CollSnapshotCallback;
      }
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

vi.mock("@/components/feed/email-card", () => ({
  EmailCard: ({ item }: { item: FolderItem }) => (
    <div data-testid="email-card">{item.from}</div>
  ),
}));

import { SubjectDetail } from "@/components/subjects/subject-detail";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

function makeFolder(): Folder {
  return {
    subject: "Acme deal",
    subjectSlug: "acme",
    folderPath: "/acme",
    pdfCount: 5,
    hasSummaryCsv: false,
    createdAt: Timestamp.fromDate(new Date()),
    updatedAt: Timestamp.fromDate(new Date()),
  };
}

function makeItem(from: string): FolderItem {
  return {
    uid: "alice",
    folderSubject: "Acme deal",
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

describe("SubjectDetail", () => {
  beforeEach(() => {
    docCallback = null;
    collCallback = null;
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
  });

  it("renders a loading state until the folder snapshot arrives", () => {
    render(withIntl(<SubjectDetail slug="acme" />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders not-found when the folder doc does not exist", () => {
    render(withIntl(<SubjectDetail slug="acme" />));
    act(() => {
      docCallback?.({ exists: () => false, data: () => makeFolder() });
    });
    expect(screen.getByText("Subject not found.")).toBeInTheDocument();
  });

  it("renders the folder header and an empty state when items list is empty", () => {
    render(withIntl(<SubjectDetail slug="acme" />));
    act(() => {
      docCallback?.({ exists: () => true, data: () => makeFolder() });
      collCallback?.({ docs: [] });
    });
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
    expect(screen.getByText("No items in this subject yet.")).toBeInTheDocument();
  });

  it("renders an 'Ask this subject' link to the ask route", () => {
    render(withIntl(<SubjectDetail slug="acme" />));
    act(() => {
      docCallback?.({ exists: () => true, data: () => makeFolder() });
      collCallback?.({ docs: [] });
    });
    const cta = screen.getByRole("link", { name: "Ask this subject" });
    expect(cta).toHaveAttribute("href", "/en/subjects/acme/ask");
  });

  it("renders one EmailCard per item when the items snapshot has rows", () => {
    render(withIntl(<SubjectDetail slug="acme" />));
    act(() => {
      docCallback?.({ exists: () => true, data: () => makeFolder() });
      collCallback?.({
        docs: [
          { id: "1", data: () => makeItem("alice@x.com") },
          { id: "2", data: () => makeItem("bob@x.com") },
        ],
      });
    });
    expect(screen.getAllByTestId("email-card")).toHaveLength(2);
  });
});
