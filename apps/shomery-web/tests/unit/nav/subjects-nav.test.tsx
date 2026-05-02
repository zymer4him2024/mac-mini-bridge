import type { ReactNode } from "react";

import type { Folder, Group } from "@shomery/shared-types";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type SnapshotCallback = (snap: {
  docs: { id: string; data: () => Folder | Group }[];
}) => void;

const callbacks: SnapshotCallback[] = [];
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
    doc: () => ({}),
    serverTimestamp: () => ({}),
    getDocs: vi.fn(async () => ({ docs: [] })),
    onSnapshot: (_q: unknown, cb: SnapshotCallback) => {
      callbacks.push(cb);
      return unsub;
    },
    setDoc: vi.fn(async () => undefined),
  };
});

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

vi.mock("@/i18n/routing", () => ({
  Link: ({
    href,
    children,
    className,
    "aria-label": ariaLabel,
  }: {
    href: string;
    children: ReactNode;
    className?: string;
    "aria-label"?: string;
  }) => (
    <a href={href} className={className} aria-label={ariaLabel}>
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

const ts = () => Timestamp.fromDate(new Date());

function makeFolder(
  subject: string,
  slug: string,
  count: number,
  unreadCount?: number,
): Folder {
  return {
    subject,
    subjectSlug: slug,
    folderPath: `/${slug}`,
    pdfCount: count,
    hasSummaryCsv: false,
    createdAt: ts(),
    updatedAt: ts(),
    ...(unreadCount !== undefined ? { unreadCount } : {}),
  };
}

function makeGroup(
  groupId: string,
  name: string,
  subjectSlugs: string[],
): Group {
  return {
    groupId,
    name,
    subjectSlugs,
    createdAt: ts(),
    updatedAt: ts(),
  };
}

function pushFolders(folders: Folder[]) {
  callbacks[0]?.({
    docs: folders.map((f) => ({ id: f.subjectSlug, data: () => f })),
  });
}

function pushGroups(groups: Group[]) {
  callbacks[1]?.({
    docs: groups.map((g) => ({ id: g.groupId, data: () => g })),
  });
}

describe("SubjectsNav", () => {
  beforeEach(() => {
    callbacks.length = 0;
    unsub.mockReset();
    if (typeof window !== "undefined") window.localStorage.clear();
  });

  afterEach(() => {
    if (typeof window !== "undefined") window.localStorage.clear();
  });

  it("renders skeleton rows before any snapshot arrives", () => {
    const { container } = render(withIntl(<SubjectsNav uid="alice" />));
    const skeletons = container.querySelectorAll('ul[aria-label="Loading…"] > li');
    expect(skeletons.length).toBe(3);
  });

  it("renders the empty state when the snapshot has zero folders", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([]);
      pushGroups([]);
    });
    expect(
      screen.getByText(
        "No subjects yet — we'll add one when your first watched email arrives.",
      ),
    ).toBeInTheDocument();
  });

  it("renders a flat list when there are no groups", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([
        makeFolder("Acme deal", "acme", 5),
        makeFolder("Q4 OKRs", "okrs", 1),
      ]);
      pushGroups([]);
    });
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
    expect(screen.getByText("Q4 OKRs")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Acme deal, 5 items" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Q4 OKRs, 1 item" }),
    ).toBeInTheDocument();
  });

  it("renders groups as collapsible parents above ungrouped subjects", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([
        makeFolder("Acme deal", "acme", 5),
        makeFolder("Q4 OKRs", "okrs", 2),
        makeFolder("Misc", "misc", 1),
      ]);
      pushGroups([makeGroup("g1", "Clients", ["acme", "okrs"])]);
    });

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse Clients",
    });
    expect(collapseBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
    expect(screen.getByText("Q4 OKRs")).toBeInTheDocument();
    expect(screen.getByText("Misc")).toBeInTheDocument();
    // "Subjects" appears twice: once as the section header at the top of
    // SubjectsNav, and once as the ungrouped subheading below the groups.
    expect(screen.getAllByText("Subjects")).toHaveLength(2);
  });

  it("collapses a group on click and persists state in localStorage", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([makeFolder("Acme deal", "acme", 5)]);
      pushGroups([makeGroup("g1", "Clients", ["acme"])]);
    });

    const collapseBtn = screen.getByRole("button", {
      name: "Collapse Clients",
    });
    act(() => {
      fireEvent.click(collapseBtn);
    });

    expect(
      screen.getByRole("button", { name: "Expand Clients" }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Acme deal")).not.toBeInTheDocument();

    const stored = window.localStorage.getItem(
      "shomery.subjectsNav.collapsedGroups",
    );
    expect(JSON.parse(stored ?? "[]")).toContain("g1");
  });

  it("silently skips members whose folder slug doesn't resolve", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([makeFolder("Acme deal", "acme", 5)]);
      pushGroups([makeGroup("g1", "Clients", ["acme", "deleted-slug"])]);
    });
    expect(screen.getByText("Acme deal")).toBeInTheDocument();
    expect(screen.queryByText("deleted-slug")).not.toBeInTheDocument();
  });

  it("renders the dual count and a brand-colored unread badge when unread > 0", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([makeFolder("Acme deal", "acme", 12, 3)]);
      pushGroups([]);
    });

    const link = screen.getByRole("link", {
      name: "Acme deal, 12 items, 3 unread",
    });
    expect(link).toBeInTheDocument();
    const unread = link.querySelector(".text-brand");
    expect(unread).not.toBeNull();
    expect(unread).toHaveTextContent("3");
  });

  it("does not render the unread span when unread is zero", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([makeFolder("Acme deal", "acme", 5, 0)]);
      pushGroups([]);
    });

    const link = screen.getByRole("link", { name: "Acme deal, 5 items" });
    expect(link.querySelector(".text-brand")).toBeNull();
  });

  it("aggregates total and unread counts on a group parent row", () => {
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([
        makeFolder("Acme deal", "acme", 10, 2),
        makeFolder("Q4 OKRs", "okrs", 5, 1),
      ]);
      pushGroups([makeGroup("g1", "Clients", ["acme", "okrs"])]);
    });

    const groupBtn = screen.getByRole("button", { name: "Collapse Clients" });
    expect(groupBtn).toHaveTextContent("15");
    expect(groupBtn).toHaveTextContent("3");
  });

  it("toggles the new-group form and creates a group on submit", async () => {
    const { setDoc } = await import("firebase/firestore");
    render(withIntl(<SubjectsNav uid="alice" />));
    act(() => {
      pushFolders([]);
      pushGroups([]);
    });

    expect(screen.queryByLabelText("Group name")).not.toBeInTheDocument();
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "New group" }));
    });
    const input = screen.getByLabelText("Group name");
    expect(input).toBeInTheDocument();

    act(() => {
      fireEvent.change(input, { target: { value: "Investors" } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Create" }));
    });

    expect(setDoc).toHaveBeenCalled();
    expect(screen.queryByLabelText("Group name")).not.toBeInTheDocument();
  });
});
