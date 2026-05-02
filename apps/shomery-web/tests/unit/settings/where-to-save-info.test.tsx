import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import enMessages from "../../../messages/en.json";

import { WhereToSaveInfo } from "@/components/settings/where-to-save-info";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("WhereToSaveInfo", () => {
  it("renders today's storage explanation, the path template, and the Drive coming-next note", () => {
    render(withIntl(<WhereToSaveInfo />));

    expect(
      screen.getByRole("heading", { name: "Where to save" }),
    ).toBeInTheDocument();

    expect(screen.getByText(/Firebase Storage, scoped to your account/)).toBeInTheDocument();

    expect(
      screen.getByText("summaries/[your account]/[subject]/[email-id].md"),
    ).toBeInTheDocument();

    expect(
      screen.getByText(/Google Drive support is in review/),
    ).toBeInTheDocument();
  });
});
