import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children }: { href: string; children: ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

import { WelcomeScreen } from "@/components/onboarding/welcome-screen";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("WelcomeScreen", () => {
  it("renders the welcome copy and a link to the connect step", () => {
    render(withIntl(<WelcomeScreen />));
    expect(
      screen.getByRole("heading", { name: "Welcome to Shomery." }),
    ).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: "Get started" });
    expect(cta.getAttribute("href")).toBe("/onboarding/connect");
  });
});
