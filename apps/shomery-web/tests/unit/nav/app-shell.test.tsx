import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const signOutOfShomery = vi.fn();
const usePathnameMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  Link: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
  usePathname: () => usePathnameMock(),
}));

vi.mock("@/lib/firebase/auth", () => ({
  signOutOfShomery: () => signOutOfShomery(),
}));

vi.mock("@/components/nav/subjects-nav", () => ({
  SubjectsNav: ({ uid }: { uid: string }) => (
    <div data-testid="subjects-nav">{uid}</div>
  ),
}));

import { AppShell } from "@/components/nav/app-shell";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    signOutOfShomery.mockReset();
    usePathnameMock.mockReset();
    usePathnameMock.mockReturnValue("/feed");
  });

  it("renders the Inbox link, Subjects header, SubjectsNav, and children", () => {
    render(
      withIntl(
        <AppShell uid="alice">
          <div data-testid="content">Hello</div>
        </AppShell>,
      ),
    );
    expect(screen.getByText("Inbox")).toBeInTheDocument();
    expect(screen.getAllByText("Subjects").length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("subjects-nav")[0]).toHaveTextContent("alice");
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("invokes signOutOfShomery when the sign-out button is clicked", async () => {
    render(
      withIntl(
        <AppShell uid="alice">
          <div />
        </AppShell>,
      ),
    );
    const [firstSignOutButton] = screen.getAllByRole("button", {
      name: "Sign out",
    });
    await userEvent.click(firstSignOutButton!);
    expect(signOutOfShomery).toHaveBeenCalled();
  });

  it("marks the Inbox link active when pathname is /feed", () => {
    usePathnameMock.mockReturnValue("/feed");
    render(
      withIntl(
        <AppShell uid="alice">
          <div />
        </AppShell>,
      ),
    );
    const inbox = screen.getByText("Inbox").closest("a")!;
    expect(inbox.className).toContain("bg-brand-tint");
  });

  it("does not mark Inbox active when on a subject page", () => {
    usePathnameMock.mockReturnValue("/subjects/acme");
    render(
      withIntl(
        <AppShell uid="alice">
          <div />
        </AppShell>,
      ),
    );
    const inbox = screen.getByText("Inbox").closest("a")!;
    expect(inbox.className).not.toContain("bg-brand-tint");
  });
});
