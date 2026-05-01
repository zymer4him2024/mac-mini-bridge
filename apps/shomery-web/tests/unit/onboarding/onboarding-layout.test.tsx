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

import OnboardingLayout from "@/app/[locale]/onboarding/layout";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("onboarding layout", () => {
  beforeEach(() => {
    replace.mockReset();
    useAuthMock.mockReset();
  });

  it("shows loading while auth is resolving", () => {
    useAuthMock.mockReturnValue({
      user: null,
      status: "loading",
      onboardingCompleted: null,
    });
    render(
      withIntl(
        <OnboardingLayout>
          <div data-testid="page">page</div>
        </OnboardingLayout>,
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
        <OnboardingLayout>
          <div>page</div>
        </OnboardingLayout>,
      ),
    );
    expect(replace).toHaveBeenCalledWith("/sign-in");
  });

  it("redirects to /feed when onboarding is already complete", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: true,
    });
    render(
      withIntl(
        <OnboardingLayout>
          <div>page</div>
        </OnboardingLayout>,
      ),
    );
    expect(replace).toHaveBeenCalledWith("/feed");
  });

  it("renders children when signed in and not yet onboarded", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
    });
    render(
      withIntl(
        <OnboardingLayout>
          <div data-testid="page">page</div>
        </OnboardingLayout>,
      ),
    );
    expect(screen.getByTestId("page")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
