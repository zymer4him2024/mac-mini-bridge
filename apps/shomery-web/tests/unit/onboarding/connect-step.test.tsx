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

import { ConnectStep } from "@/components/onboarding/connect-step";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("ConnectStep", () => {
  it("renders the explainer and a Continue link to the watch step", () => {
    render(withIntl(<ConnectStep />));
    expect(
      screen.getByRole("heading", { name: "Your inbox is connected." }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Continue" }).getAttribute("href"),
    ).toBe("/onboarding/watch");
  });
});
