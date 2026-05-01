import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const setDocMock = vi.fn();
const pushMock = vi.fn();
const useAuthMock = vi.fn();

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

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

import { WatchStep } from "@/components/onboarding/watch-step";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("WatchStep", () => {
  beforeEach(() => {
    setDocMock.mockReset();
    setDocMock.mockResolvedValue(undefined);
    pushMock.mockReset();
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
    });
  });

  it("blocks Continue with an inline message when the list is empty", async () => {
    render(withIntl(<WatchStep />));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Add at least one sender or domain to continue.",
    );
    expect(setDocMock).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("persists entries and advances to /onboarding/save", async () => {
    render(withIntl(<WatchStep />));
    await userEvent.type(
      screen.getByPlaceholderText("alice@example.com or @acme.com"),
      "alice@example.com",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(setDocMock).toHaveBeenCalledOnce());
    expect(setDocMock).toHaveBeenCalledWith(
      expect.anything(),
      { priorityWatchSenders: ["alice@example.com"] },
      { merge: true },
    );
    expect(pushMock).toHaveBeenCalledWith("/onboarding/save");
  });

  it("surfaces a save error and does not navigate", async () => {
    setDocMock.mockRejectedValueOnce(new Error("permission-denied"));
    render(withIntl(<WatchStep />));
    await userEvent.type(
      screen.getByPlaceholderText("alice@example.com or @acme.com"),
      "@acme.com",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't save your list. Please try again.",
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});
