import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const mockToasts: { id: string; item: Record<string, unknown> }[] = [];
const dismiss = vi.fn();

vi.mock("@/lib/use-new-item-toasts", () => ({
  useNewItemToasts: () => ({ toasts: mockToasts, dismiss }),
}));

import { FeedToastStack } from "@/components/feed/feed-toast";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

function pushToast(overrides: Partial<{ id: string; item: Record<string, unknown> }> = {}) {
  mockToasts.push({
    id: overrides.id ?? "abc",
    item: {
      uid: "alice",
      folderSubject: "Acme deal",
      folderSlug: "acme-deal",
      from: "Acme <deals@acme.com>",
      keyPoints: [],
      asks: [],
      urgency: "low",
      ...(overrides.item ?? {}),
    },
  });
}

describe("FeedToastStack", () => {
  beforeEach(() => {
    mockToasts.length = 0;
    dismiss.mockReset();
  });

  it("renders nothing when there are no toasts", () => {
    const { container } = render(withIntl(<FeedToastStack uid="alice" />));
    expect(container.firstChild).toBeNull();
  });

  it("renders one card per toast with the new-email label, sender, and subject", () => {
    pushToast({ id: "abc" });
    render(withIntl(<FeedToastStack uid="alice" />));
    expect(screen.getByText("New email")).toBeInTheDocument();
    expect(screen.getByText(/Acme <deals@acme.com>/)).toBeInTheDocument();
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
  });

  it("links to the item route when markdownStoragePath is present", () => {
    pushToast({
      id: "abc",
      item: {
        markdownStoragePath: "summaries/alice/acme-deal/abc.md",
      },
    });
    render(withIntl(<FeedToastStack uid="alice" />));
    const link = screen
      .getByText(/Acme <deals@acme.com>/)
      .closest("a");
    expect(link?.getAttribute("href")).toBe(
      "/en/subjects/acme-deal/items/abc",
    );
  });

  it("falls back to the subject route when markdown is not yet emitted", () => {
    pushToast({ id: "abc" });
    render(withIntl(<FeedToastStack uid="alice" />));
    const link = screen.getByText(/Acme <deals@acme.com>/).closest("a");
    expect(link?.getAttribute("href")).toBe("/en/subjects/acme-deal");
  });

  it("calls dismiss when the X button is clicked", async () => {
    pushToast({ id: "abc" });
    render(withIntl(<FeedToastStack uid="alice" />));
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(dismiss).toHaveBeenCalledWith("abc");
  });
});
