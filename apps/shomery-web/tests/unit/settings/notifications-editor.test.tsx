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

  it("renders all five channel rows with Telegram as Coming soon", () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    expect(screen.getByText("Email digest")).toBeInTheDocument();
    expect(screen.getByText("KakaoTalk")).toBeInTheDocument();
    expect(screen.getByText("WhatsApp")).toBeInTheDocument();
    expect(screen.getByText("Telegram")).toBeInTheDocument();
    expect(screen.getByText("SMS")).toBeInTheDocument();
    expect(screen.getAllByText("Coming soon")).toHaveLength(4);
    expect(screen.queryByLabelText("Chat ID")).not.toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: "Telegram" }),
    ).toBeDisabled();
  });

  it("disables the Save button until something changes", () => {
    render(
      withIntl(<NotificationsEditor uid="alice" initial={DEFAULT_INITIAL} />),
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("toggles the Email digest switch and persists only digestEnabled", async () => {
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
      { digestEnabled: false },
      { merge: true },
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
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
