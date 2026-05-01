import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const getDownloadURL = vi.fn();

vi.mock("firebase/storage", () => ({
  getDownloadURL: (...args: unknown[]) => getDownloadURL(...args),
  ref: (_storage: unknown, path: string) => ({ path }),
}));

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseStorage: () => ({}),
}));

import { PdfLink } from "@/components/feed/pdf-link";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("PdfLink", () => {
  beforeEach(() => {
    getDownloadURL.mockReset();
  });

  it("renders the filename as a static badge while the URL is loading", () => {
    getDownloadURL.mockReturnValue(new Promise(() => {}));
    render(
      withIntl(<PdfLink storagePath="users/a/folders/x/y.pdf" filename="y.pdf" />),
    );
    expect(screen.getByText(/y\.pdf/)).toHaveAttribute("aria-busy", "true");
  });

  it("renders an anchor with the resolved download URL once available", async () => {
    getDownloadURL.mockResolvedValueOnce("https://example.com/y.pdf");
    render(
      withIntl(<PdfLink storagePath="users/a/folders/x/y.pdf" filename="y.pdf" />),
    );
    const link = await waitFor(() =>
      screen.getByRole("link", { name: /y\.pdf/ }),
    );
    expect(link).toHaveAttribute("href", "https://example.com/y.pdf");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("keeps the static badge when getDownloadURL rejects", async () => {
    getDownloadURL.mockRejectedValueOnce(new Error("not-found"));
    render(
      withIntl(<PdfLink storagePath="users/a/folders/x/missing.pdf" filename="missing.pdf" />),
    );
    await waitFor(() =>
      expect(screen.queryByRole("link")).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/missing\.pdf/)).toBeInTheDocument();
  });
});
