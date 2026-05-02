import type { ReactNode } from "react";
import { useEffect } from "react";

import { act, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const useAuthMock = vi.fn();

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

let lastUnreadHook: ((n: number) => void) | null = null;

vi.mock("@/components/feed/feed-list", () => ({
  FeedList: ({
    uid,
    onUnreadCount,
  }: {
    uid: string;
    onUnreadCount?: (n: number) => void;
  }) => {
    useEffect(() => {
      lastUnreadHook = onUnreadCount ?? null;
    }, [onUnreadCount]);
    return <div data-testid="feed-list">{uid}</div>;
  },
}));

import { FeedScreen } from "@/components/feed/feed-screen";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("FeedScreen", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    lastUnreadHook = null;
  });

  it("renders a loading message while auth status is resolving", () => {
    useAuthMock.mockReturnValue({ user: null, status: "loading" });
    render(withIntl(<FeedScreen />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders a loading message when signed out (layout will redirect)", () => {
    useAuthMock.mockReturnValue({ user: null, status: "signed-out" });
    render(withIntl(<FeedScreen />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders the feed list with the user's uid when signed in", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<FeedScreen />));
    expect(screen.getByTestId("feed-list")).toHaveTextContent("alice");
  });

  it("hides the processed subtitle when unread count is zero", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<FeedScreen />));
    expect(screen.queryByText(/processed/i)).not.toBeInTheDocument();
  });

  it("renders the processed subtitle when FeedList reports unread > 0", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<FeedScreen />));
    act(() => {
      lastUnreadHook?.(5);
    });
    expect(
      screen.getByText(
        "5 new emails processed · saved to your private vault.",
      ),
    ).toBeInTheDocument();
  });
});
