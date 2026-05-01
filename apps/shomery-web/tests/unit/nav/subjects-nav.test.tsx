import type { ReactNode } from "react";

import type { Folder } from "@shomery/shared-types";
import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type SnapshotCallback = (snap: {
  docs: { id: string; data: () => Folder }[];
}) => void;

let lastCallback: SnapshotCallback | null = null;
const unsub = vi.fn();

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    collection: () => ({}),
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

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
  usePathname: () => "/feed",
}));

import { SubjectsNav } from "@/components/nav/subjects-nav";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

function makeFolder(subject: string, slug: string, count: number): Folder {
  return {
    subject,
    subjectSlug: slug,
    folderPath: `/${slug}`,
    pdfCount: count,
    hasSummaryCsv: false,
    createdAt: Timestamp.fromDate(new Date()),
    updatedAt: Timestamp.fromDate(new Date()),
  };
}

describe("SubjectsNav", () => {
  beforeEach(() => {
    lastCallback = null;
    unsub.mockReset();
  });

  it("renders skeleton rows before any snapshot arrives", () => {
    const { container } = render(withIntl(<SubjectsNav uid="alice" />));
    const skeletons = container.querySelectorAll('[aria-hidden="true"]');
    expect(skeletons.length).toBe(3);
  });

  it("renders the empty state when the snapshot has zero folders", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      lastCallback?.({ docs: [] });
    });
    expect(
      screen.getByText(
        "No subjects yet — we'll add one when your first watched email arrives.",
      ),
    ).toBeInTheDocument();
  });

  it("renders one link per folder with subject and item-count badge", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      lastCallback?.({
        docs: [
          { id: "acme", data: () => makeFolder("Acme deal", "acme", 5) },
          { id: "okrs", data: () => makeFolder("Q4 OKRs", "okrs", 1) },
        ],
      });
    });
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
    expect(screen.getByText("5 items")).toBeInTheDocument();
    expect(screen.getByText("Q4 OKRs")).toBeInTheDocument();
    expect(screen.getByText("1 item")).toBeInTheDocument();
  });
});
