import type { ReactNode } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { render, screen, waitFor } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const getMarkdownMock = vi.fn();

vi.mock("@/lib/markdown", async () => {
  const actual = await vi.importActual<typeof import("@/lib/markdown")>(
    "@/lib/markdown",
  );
  return {
    ...actual,
    getMarkdown: (...args: unknown[]) => getMarkdownMock(...args),
  };
});

import { MarkdownViewer } from "@/components/feed/markdown-viewer";
import {
  MarkdownDriveNotReadyError,
  MarkdownNotEmittedError,
} from "@/lib/markdown";

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
    pdfFilename: "acme.pdf",
    createdAt: Timestamp.fromDate(new Date()),
    ...overrides,
  };
}

describe("MarkdownViewer", () => {
  beforeEach(() => {
    getMarkdownMock.mockReset();
  });

  it("renders the loading state immediately", () => {
    getMarkdownMock.mockReturnValue(new Promise(() => {}));
    render(withIntl(<MarkdownViewer item={makeItem()} />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders the empty state when the item has no markdownStoragePath", async () => {
    getMarkdownMock.mockRejectedValueOnce(new MarkdownNotEmittedError());
    render(withIntl(<MarkdownViewer item={makeItem()} />));
    expect(
      await screen.findByText(/has no markdown summary yet/),
    ).toBeInTheDocument();
  });

  it("renders the drive-not-ready state for drive:// paths", async () => {
    getMarkdownMock.mockRejectedValueOnce(new MarkdownDriveNotReadyError());
    render(withIntl(<MarkdownViewer item={makeItem()} />));
    expect(
      await screen.findByText(/Drive support is coming soon/),
    ).toBeInTheDocument();
  });

  it("renders an alert when fetching the markdown fails", async () => {
    getMarkdownMock.mockRejectedValueOnce(new Error("network"));
    render(withIntl(<MarkdownViewer item={makeItem()} />));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't load this summary. Please try again.",
    );
  });

  it("renders the rendered markdown when the fetch succeeds", async () => {
    getMarkdownMock.mockResolvedValueOnce(
      "# Acme deal\n\n- term sheet\n- sign by friday",
    );
    render(withIntl(<MarkdownViewer item={makeItem()} />));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Acme deal" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("term sheet")).toBeInTheDocument();
    expect(screen.getByText("sign by friday")).toBeInTheDocument();
  });
});
