import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const replace = vi.fn();
const useAuthMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock("@/components/nav/app-shell", () => ({
  AppShell: ({ uid, children }: { uid: string; children: ReactNode }) => (
    <div data-testid="app-shell" data-uid={uid}>
      {children}
    </div>
  ),
}));

import AppGroupLayout from "@/app/[locale]/(app)/layout";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("(app) layout", () => {
  beforeEach(() => {
    replace.mockReset();
    useAuthMock.mockReset();
  });

  it("renders a loading state while auth is resolving and does not redirect", () => {
    useAuthMock.mockReturnValue({
      user: null,
      status: "loading",
      onboardingCompleted: null,
    });
    render(
      withIntl(
        <AppGroupLayout>
          <div>child</div>
        </AppGroupLayout>,
      ),
    );
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("renders a loading state while the onboarding flag is resolving", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: null,
    });
    render(
      withIntl(
        <AppGroupLayout>
          <div>child</div>
        </AppGroupLayout>,
      ),
    );
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to /sign-in when signed out", () => {
    useAuthMock.mockReturnValue({
      user: null,
      status: "signed-out",
      onboardingCompleted: null,
    });
    render(
      withIntl(
        <AppGroupLayout>
          <div>child</div>
        </AppGroupLayout>,
      ),
    );
    expect(replace).toHaveBeenCalledWith("/sign-in");
  });

  it("redirects to /onboarding when signed in but not yet onboarded", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
    });
    render(
      withIntl(
        <AppGroupLayout>
          <div>child</div>
        </AppGroupLayout>,
      ),
    );
    expect(replace).toHaveBeenCalledWith("/onboarding");
  });

  it("renders the AppShell with children when signed in and onboarded", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: true,
    });
    render(
      withIntl(
        <AppGroupLayout>
          <div data-testid="page-child">child</div>
        </AppGroupLayout>,
      ),
    );
    const shell = screen.getByTestId("app-shell");
    expect(shell.getAttribute("data-uid")).toBe("alice");
    expect(screen.getByTestId("page-child")).toBeInTheDocument();
  });
});
