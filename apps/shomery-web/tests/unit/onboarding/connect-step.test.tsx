import type { ReactNode } from "react";

import { act, render, screen } from "@testing-library/react";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const useAuthMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

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

import { ConnectStep } from "@/components/onboarding/connect-step";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("ConnectStep", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    lastCallback = null;
    unsub.mockReset();
  });

  it("renders the pending copy when gmail.email is unset", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: null,
    });
    render(withIntl(<ConnectStep />));
    expect(
      screen.getByRole("heading", { name: "Setting up your inbox." }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Continue" }).getAttribute("href"),
    ).toBe("/onboarding/watch");
  });

  it("renders the connected copy and badge when gmail.email is set", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<ConnectStep />));
    expect(
      screen.getByRole("heading", { name: "Your inbox is connected." }),
    ).toBeInTheDocument();
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("Connected as alice@example.com");
  });

  it("renders 'first summary waiting' when connected and the items query is empty", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<ConnectStep />));
    act(() => {
      lastCallback?.({ empty: true, docs: [] });
    });
    expect(
      screen.getByText(
        "Watching — your first summary will land here soon.",
      ),
    ).toBeInTheDocument();
  });

  it("renders the latest-summary line when connected and an item exists", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<ConnectStep />));
    act(() => {
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
      lastCallback?.({
        empty: false,
        docs: [{ data: () => ({ createdAt: Timestamp.fromDate(fiveMinutesAgo) }) }],
      });
    });
    expect(screen.getByText(/^Latest summary /)).toBeInTheDocument();
  });

  it("does not subscribe to items while gmail.email is unset", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: null,
    });
    render(withIntl(<ConnectStep />));
    expect(lastCallback).toBeNull();
  });
});
