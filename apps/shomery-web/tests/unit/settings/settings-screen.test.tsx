import type { ReactNode } from "react";

import { act, render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

type DocSnapshotCallback = (snap: {
  exists: () => boolean;
  data: () => Record<string, unknown>;
}) => void;

type QuerySnapshotCallback = (snap: {
  docs: { id: string; data: () => Record<string, unknown> }[];
}) => void;

let lastCallback: DocSnapshotCallback | null = null;

const isDocRef = (ref: unknown): boolean =>
  Boolean(ref && typeof ref === "object" && (ref as { __doc?: boolean }).__doc);

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    doc: () => ({ __doc: true }),
    collection: () => ({ __collection: true }),
    query: () => ({ __query: true }),
    orderBy: () => ({}),
    limit: () => ({}),
    onSnapshot: (
      ref: unknown,
      cb: DocSnapshotCallback | QuerySnapshotCallback,
    ) => {
      if (isDocRef(ref)) {
        lastCallback = cb as DocSnapshotCallback;
      }
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

vi.mock("@/components/settings/watched-senders-editor", () => ({
  WatchedSendersEditor: ({
    uid,
    initial,
  }: {
    uid: string;
    initial: string[];
  }) => (
    <div data-testid="watched-senders-editor" data-uid={uid}>
      {initial.join(",")}
    </div>
  ),
}));

vi.mock("@/components/settings/notifications-editor", () => ({
  NotificationsEditor: ({
    uid,
    initial,
  }: {
    uid: string;
    initial: {
      digestEnabled: boolean;
      telegramEnabled: boolean;
      telegramChatId: string;
    };
  }) => (
    <div
      data-testid="notifications-editor"
      data-uid={uid}
      data-digest={String(initial.digestEnabled)}
      data-telegram={String(initial.telegramEnabled)}
      data-chatid={initial.telegramChatId}
    />
  ),
}));

vi.mock("@/components/settings/privacy-data-editor", () => ({
  PrivacyDataEditor: ({ uid }: { uid: string }) => (
    <div data-testid="privacy-data-editor" data-uid={uid} />
  ),
}));

vi.mock("@/components/settings/groups-editor", () => ({
  GroupsEditor: ({ uid }: { uid: string }) => (
    <div data-testid="groups-editor" data-uid={uid} />
  ),
}));

import { SettingsScreen } from "@/components/settings/settings-screen";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("SettingsScreen", () => {
  beforeEach(() => {
    lastCallback = null;
    useAuthMock.mockReset();
  });

  it("renders the loading state while auth resolves", () => {
    useAuthMock.mockReturnValue({ user: null, status: "loading" });
    render(withIntl(<SettingsScreen />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders the loading state until the config snapshot arrives", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<SettingsScreen />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders both editors with seeded values when the config doc exists", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<SettingsScreen />));
    act(() => {
      lastCallback?.({
        exists: () => true,
        data: () => ({
          priorityWatchSenders: ["@acme.com"],
          digestEnabled: false,
          telegramEnabled: true,
          telegramChatId: "12345",
        }),
      });
    });
    const watched = screen.getByTestId("watched-senders-editor");
    expect(watched.getAttribute("data-uid")).toBe("alice");
    expect(watched).toHaveTextContent("@acme.com");
    const notifications = screen.getByTestId("notifications-editor");
    expect(notifications.getAttribute("data-digest")).toBe("false");
    expect(notifications.getAttribute("data-telegram")).toBe("true");
    expect(notifications.getAttribute("data-chatid")).toBe("12345");
  });

  it("renders both editors with defaults when the config doc is missing", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<SettingsScreen />));
    act(() => {
      lastCallback?.({ exists: () => false, data: () => ({}) });
    });
    expect(screen.getByTestId("watched-senders-editor")).toBeInTheDocument();
    const notifications = screen.getByTestId("notifications-editor");
    expect(notifications.getAttribute("data-digest")).toBe("true");
    expect(notifications.getAttribute("data-telegram")).toBe("false");
    expect(notifications.getAttribute("data-chatid")).toBe("");
  });
});
