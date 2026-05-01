import type { ReactNode } from "react";

import type { FolderItem } from "@shomery/shared-types";
import { render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

vi.mock("@/components/feed/pdf-link", () => ({
  PdfLink: ({ filename }: { filename: string }) => (
    <span data-testid="pdf-link">{filename}</span>
  ),
}));

import { EmailCard } from "@/components/feed/email-card";

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
    keyPoints: ["Term sheet attached", "Sign by Friday"],
    asks: [],
    suggestedResponse: "",
    pdfFilename: "acme.pdf",
    createdAt: Timestamp.fromDate(new Date(Date.now() - 60 * 60 * 1000)),
    ...overrides,
  };
}

describe("EmailCard", () => {
  it("renders sender, subject, and key points", () => {
    render(withIntl(<EmailCard item={makeItem()} />));
    expect(screen.getByText(/Acme <deals@acme.com>/)).toBeInTheDocument();
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
    expect(screen.getByText("Term sheet attached")).toBeInTheDocument();
    expect(screen.getByText("Sign by Friday")).toBeInTheDocument();
  });

  it("shows the HIGH urgency pill in warn color for high-priority items", () => {
    render(withIntl(<EmailCard item={makeItem({ urgency: "high" })} />));
    const pill = screen.getByText("HIGH");
    expect(pill).toBeInTheDocument();
    expect(pill.className).toMatch(/text-warn/);
  });

  it("shows the LOW urgency pill in soft color for low-priority items", () => {
    render(withIntl(<EmailCard item={makeItem({ urgency: "low" })} />));
    const pill = screen.getByText("LOW");
    expect(pill).toBeInTheDocument();
    expect(pill.className).toMatch(/text-soft/);
  });

  it("falls back to 'Unknown sender' when from is empty", () => {
    render(withIntl(<EmailCard item={makeItem({ from: "" })} />));
    expect(screen.getByText(/Unknown sender/)).toBeInTheDocument();
  });

  it("omits the PDF link when pdfStoragePath is missing", () => {
    render(withIntl(<EmailCard item={makeItem()} />));
    expect(screen.queryByTestId("pdf-link")).not.toBeInTheDocument();
  });

  it("renders the PDF link when pdfStoragePath is present", () => {
    render(
      withIntl(
        <EmailCard
          item={makeItem({ pdfStoragePath: "users/alice/folders/acme/acme.pdf" })}
        />,
      ),
    );
    expect(screen.getByTestId("pdf-link")).toHaveTextContent("acme.pdf");
  });

  it("renders gracefully when keyPoints is empty", () => {
    render(withIntl(<EmailCard item={makeItem({ keyPoints: [] })} />));
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("omits the Read full link when markdownStoragePath is missing", () => {
    render(withIntl(<EmailCard item={makeItem()} itemId="abc123" />));
    expect(screen.queryByText(/Read full/)).not.toBeInTheDocument();
  });

  it("omits the Read full link when itemId is missing", () => {
    render(
      withIntl(
        <EmailCard
          item={makeItem({
            markdownStoragePath: "summaries/alice/acme/abc123.md",
          })}
        />,
      ),
    );
    expect(screen.queryByText(/Read full/)).not.toBeInTheDocument();
  });

  it("renders the Read full link pointing at the item route", () => {
    render(
      withIntl(
        <EmailCard
          item={makeItem({
            markdownStoragePath: "summaries/alice/acme-deal/abc123.md",
          })}
          itemId="abc123"
        />,
      ),
    );
    const link = screen.getByText(/Read full/);
    expect(link).toBeInTheDocument();
    expect(link.closest("a")?.getAttribute("href")).toBe(
      "/en/subjects/acme-deal/items/abc123",
    );
  });
});
