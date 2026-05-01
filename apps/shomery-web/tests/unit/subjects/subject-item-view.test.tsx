import type { ReactNode } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type DocSnapshotCallback = (snap: {
  exists: () => boolean;
  data: () => FolderItem;
}) => void;

let docCallback: DocSnapshotCallback | null = null;

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    doc: () => ({}),
    onSnapshot: (_ref: unknown, cb: DocSnapshotCallback) => {
      docCallback = cb;
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

vi.mock("@/components/feed/markdown-viewer", () => ({
  MarkdownViewer: ({ item }: { item: FolderItem }) => (
    <div data-testid="markdown-viewer">{item.folderSubject}</div>
  ),
}));

vi.mock("@/components/feed/pdf-link", () => ({
  PdfLink: ({ filename }: { filename: string }) => (
    <span data-testid="pdf-link">{filename}</span>
  ),
}));

import { SubjectItemView } from "@/components/subjects/subject-item-view";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

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
    pdfFilename: "",
    createdAt: Timestamp.fromDate(new Date()),
    ...overrides,
  };
}

describe("SubjectItemView", () => {
  beforeEach(() => {
    docCallback = null;
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
  });

  it("renders the loading state before the snapshot arrives", () => {
    render(withIntl(<SubjectItemView slug="acme-deal" itemId="abc" />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders the not-found state when the item doc is missing", () => {
    render(withIntl(<SubjectItemView slug="acme-deal" itemId="abc" />));
    act(() => {
      docCallback?.({ exists: () => false, data: () => makeItem() });
    });
    expect(
      screen.getByText("We couldn't find this email."),
    ).toBeInTheDocument();
  });

  it("renders the header card and the markdown viewer when the item exists", () => {
    render(withIntl(<SubjectItemView slug="acme-deal" itemId="abc" />));
    act(() => {
      docCallback?.({ exists: () => true, data: () => makeItem() });
    });
    expect(screen.getByText(/Acme <deals@acme.com>/)).toBeInTheDocument();
    expect(screen.getByTestId("markdown-viewer")).toHaveTextContent(
      "Acme deal",
    );
  });

  it("renders the PDF link when pdfStoragePath is present", () => {
    render(withIntl(<SubjectItemView slug="acme-deal" itemId="abc" />));
    act(() => {
      docCallback?.({
        exists: () => true,
        data: () =>
          makeItem({
            pdfStoragePath: "pdfs/alice/abc.pdf",
            pdfFilename: "abc.pdf",
          }),
      });
    });
    expect(screen.getByTestId("pdf-link")).toHaveTextContent("abc.pdf");
  });
});
