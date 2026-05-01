import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
const useAuthMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
}));

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

import { RootRedirect } from "@/app/[locale]/root-redirect";

describe("RootRedirect", () => {
  beforeEach(() => {
    replace.mockReset();
    useAuthMock.mockReset();
  });

  it("does not redirect while auth is still loading", () => {
    useAuthMock.mockReturnValue({
      user: null,
      status: "loading",
      onboardingCompleted: null,
    });
    render(<RootRedirect />);
    expect(replace).not.toHaveBeenCalled();
  });

  it("does not redirect while onboarding state is loading", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: null,
    });
    render(<RootRedirect />);
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to /feed when signed in and onboarded", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: true,
    });
    render(<RootRedirect />);
    expect(replace).toHaveBeenCalledWith("/feed");
  });

  it("redirects to /onboarding when signed in and not yet onboarded", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
    });
    render(<RootRedirect />);
    expect(replace).toHaveBeenCalledWith("/onboarding");
  });

  it("redirects to /sign-in when signed out", () => {
    useAuthMock.mockReturnValue({
      user: null,
      status: "signed-out",
      onboardingCompleted: null,
    });
    render(<RootRedirect />);
    expect(replace).toHaveBeenCalledWith("/sign-in");
  });
});
