import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const setDocMock = vi.fn();

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    doc: () => ({}),
    setDoc: (...args: unknown[]) => setDocMock(...args),
  };
});

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

import { NotificationsEditor } from "@/components/settings/notifications-editor";

const DEFAULT_INITIAL = {
  digestEnabled: true,
  telegramEnabled: false,
  telegramChatId: "",
};

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("NotificationsEditor", () => {
  beforeEach(() => {
    setDocMock.mockReset();
    setDocMock.mockResolvedValue(undefined);
  });

  it("renders all five channel rows", () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    expect(screen.getByText("Email digest")).toBeInTheDocument();
    expect(screen.getByText("KakaoTalk")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp")).toBeInTheDocument();
    expect(screen.getByText("Telegram")).toBeInTheDocument();
    expect(screen.getByText("SMS")).toBeInTheDocument();
    expect(screen.getAllByText("Coming soon")).toHaveLength(3);
  });

  it("disables the Save button until something changes", () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("toggles the Email digest switch and persists the change", async () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    await userEvent.click(
      screen.getByRole("switch", { name: "Disable Email digest" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(setDocMock).toHaveBeenCalledOnce());
    expect(setDocMock).toHaveBeenCalledWith(
      expect.anything(),
      {
        digestEnabled: false,
        telegramEnabled: false,
        telegramChatId: "",
      },
      { merge: true },
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("enables Telegram, accepts a chat id, and persists both fields", async () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    await userEvent.click(
      screen.getByRole("switch", { name: "Enable Telegram" }),
    );
    await userEvent.type(
      screen.getByLabelText("Chat ID"),
      "987654321",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(setDocMock).toHaveBeenCalledOnce());
    expect(setDocMock).toHaveBeenCalledWith(
      expect.anything(),
      {
        digestEnabled: true,
        telegramEnabled: true,
        telegramChatId: "987654321",
      },
      { merge: true },
    );
  });

  it("blocks save and surfaces a hint when Telegram is on but chat id is empty", async () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    await userEvent.click(
      screen.getByRole("switch", { name: "Enable Telegram" }),
    );
    expect(
      await screen.findByText(
        "Add a Telegram chat ID to enable this channel.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
    expect(setDocMock).not.toHaveBeenCalled();
  });

  it("surfaces an inline error when setDoc rejects", async () => {
    setDocMock.mockRejectedValueOnce(new Error("permission-denied"));
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    await userEvent.click(
      screen.getByRole("switch", { name: "Disable Email digest" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't save your changes. Please try again.",
    );
  });
});
