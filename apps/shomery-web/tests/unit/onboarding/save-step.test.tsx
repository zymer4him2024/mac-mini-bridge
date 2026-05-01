import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const markMock = vi.fn();
const pushMock = vi.fn();
const useAuthMock = vi.fn();

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
  markOnboardingCompleted: (uid: string) => markMock(uid),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
}));

import { SaveStep } from "@/components/onboarding/save-step";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("SaveStep", () => {
  beforeEach(() => {
    markMock.mockReset();
    markMock.mockResolvedValue(undefined);
    pushMock.mockReset();
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
    });
  });

  it("marks onboarding complete and navigates to /feed", async () => {
    render(withIntl(<SaveStep />));
    await userEvent.click(
      screen.getByRole("button", { name: "Start watching" }),
    );
    await waitFor(() => expect(markMock).toHaveBeenCalledWith("alice"));
    expect(pushMock).toHaveBeenCalledWith("/feed");
  });

  it("surfaces a completion error and does not navigate", async () => {
    markMock.mockRejectedValueOnce(new Error("offline"));
    render(withIntl(<SaveStep />));
    await userEvent.click(
      screen.getByRole("button", { name: "Start watching" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't finish setup. Please try again.",
    );
    expect(pushMock).not.toHaveBeenCalled();
  });
});
