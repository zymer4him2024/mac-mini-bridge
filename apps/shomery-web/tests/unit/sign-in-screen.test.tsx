import type { ReactNode } from "react";

import { FirebaseError } from "firebase/app";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../messages/en.json";

const replace = vi.fn();
const signInWithGoogle = vi.fn();
const useAuthMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
  signInWithGoogle: () => signInWithGoogle(),
}));

import { SignInScreen } from "@/app/[locale]/sign-in/sign-in-screen";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("SignInScreen", () => {
  beforeEach(() => {
    replace.mockReset();
    signInWithGoogle.mockReset();
    useAuthMock.mockReset();
    useAuthMock.mockReturnValue({ user: null, status: "signed-out" });
  });

  it("renders the brand headline and primary button", () => {
    render(withIntl(<SignInScreen />));
    expect(screen.getByText("Read once. Ask anything.")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Continue with Google" }),
    ).toBeInTheDocument();
  });

  it("redirects signed-in users to the feed", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
    });
    render(withIntl(<SignInScreen />));
    expect(replace).toHaveBeenCalledWith("/feed");
  });

  it("calls signInWithGoogle on click and shows the pending label", async () => {
    let resolve!: () => void;
    signInWithGoogle.mockImplementation(
      () => new Promise<void>((r) => (resolve = r)),
    );
    render(withIntl(<SignInScreen />));
    await userEvent.click(
      screen.getByRole("button", { name: "Continue with Google" }),
    );
    expect(
      screen.getByRole("button", { name: "Signing in…" }),
    ).toBeInTheDocument();
    await act(async () => {
      resolve();
    });
  });

  it("stays silent when sign-in is cancelled by the user", async () => {
    signInWithGoogle.mockRejectedValueOnce(
      new FirebaseError("auth/popup-closed-by-user", "cancelled"),
    );
    render(withIntl(<SignInScreen />));
    await userEvent.click(
      screen.getByRole("button", { name: "Continue with Google" }),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Continue with Google" }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an inline error on unexpected sign-in failures", async () => {
    signInWithGoogle.mockRejectedValueOnce(new Error("network"));
    render(withIntl(<SignInScreen />));
    await userEvent.click(
      screen.getByRole("button", { name: "Continue with Google" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Sign-in didn't go through. Please try again.",
    );
  });
});
