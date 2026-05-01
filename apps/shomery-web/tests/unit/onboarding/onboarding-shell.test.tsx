import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import enMessages from "../../../messages/en.json";

import { OnboardingShell } from "@/components/onboarding/onboarding-shell";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("OnboardingShell", () => {
  it("renders children for the welcome screen without a progress bar", () => {
    render(
      withIntl(
        <OnboardingShell step="welcome">
          <p data-testid="content">Hello</p>
        </OnboardingShell>,
      ),
    );
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders a progressbar with the current step label for numbered steps", () => {
    render(
      withIntl(
        <OnboardingShell step={2}>
          <p>step body</p>
        </OnboardingShell>,
      ),
    );
    const bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("2");
    expect(bar.getAttribute("aria-valuemax")).toBe("3");
    expect(screen.getByText("Step 2 of 3")).toBeInTheDocument();
  });
});
