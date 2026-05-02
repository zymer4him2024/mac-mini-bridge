import type { ReactNode } from "react";

import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const useAuthMock = vi.fn();

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

type SnapshotCallback = (snap: {
  empty: boolean;
  docs: { data: () => { createdAt?: Timestamp } }[];
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

import { InboxStatusInfo } from "@/components/settings/inbox-status-info";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("InboxStatusInfo", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    lastCallback = null;
    unsub.mockReset();
  });

  it("renders the pending copy when gmail.email is unset", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      gmailEmail: null,
    });
    render(withIntl(<InboxStatusInfo />));
    expect(
      screen.getByRole("heading", { name: "Inbox" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Setting up")).toBeInTheDocument();
    expect(
      screen.getByText(
        "We're connecting Gmail watching for your account. Once it's wired, your sender will show here.",
      ),
    ).toBeInTheDocument();
    expect(lastCallback).toBeNull();
  });

  it("renders the connected line when gmail.email is set", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<InboxStatusInfo />));
    expect(screen.getByText("Gmail")).toBeInTheDocument();
    expect(
      screen.getByText("Connected as alice@example.com"),
    ).toBeInTheDocument();
  });

  it("does not render the latest-summary block while items are still loading", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<InboxStatusInfo />));
    expect(screen.queryByText("Latest summary")).not.toBeInTheDocument();
  });

  it("renders 'first summary waiting' when connected and the items query is empty", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<InboxStatusInfo />));
    act(() => {
      lastCallback?.({ empty: true, docs: [] });
    });
    expect(screen.getByText("Latest summary")).toBeInTheDocument();
    expect(
      screen.getByText("Watching — your first summary will land here soon."),
    ).toBeInTheDocument();
  });

  it("renders the latest-summary timestamp when connected and an item exists", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<InboxStatusInfo />));
    act(() => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      lastCallback?.({
        empty: false,
        docs: [
          { data: () => ({ createdAt: Timestamp.fromDate(fiveMinutesAgo) }) },
        ],
      });
    });
    expect(screen.getByText("Latest summary")).toBeInTheDocument();
    expect(
      screen.queryByText("Watching — your first summary will land here soon."),
    ).not.toBeInTheDocument();
  });
});
