import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const useAuthMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/firebase/auth", () => ({
  useAuth: () => useAuthMock(),
}));

import { ConnectStep } from "@/components/onboarding/connect-step";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("ConnectStep", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
  });

  it("renders the explainer and a Continue link to the watch step", () => {
    useAuthMock.mockReturnValue({
      user: null,
      status: "loading",
      onboardingCompleted: null,
      gmailEmail: null,
    });
    render(withIntl(<ConnectStep />));
    expect(
      screen.getByRole("heading", { name: "Your inbox is connected." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Continue" }).getAttribute("href"),
    ).toBe("/onboarding/watch");
  });

  it("does not render a connected badge when gmail.email is unset", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: null,
    });
    render(withIntl(<ConnectStep />));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders the connected badge when gmail.email is set", () => {
    useAuthMock.mockReturnValue({
      user: { uid: "alice" },
      status: "signed-in",
      onboardingCompleted: false,
      gmailEmail: "alice@example.com",
    });
    render(withIntl(<ConnectStep />));
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("Connected as alice@example.com");
  });
});
