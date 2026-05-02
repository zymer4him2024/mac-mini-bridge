import type { ReactNode } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const signOutOfShomery = vi.fn();
const usePathnameMock = vi.fn();

vi.mock("@/i18n/routing", () => ({
  Link: ({
    href,
    children,
    className,
    "aria-label": ariaLabel,
  }: {
    href: string;
    children: ReactNode;
    className?: string;
    "aria-label"?: string;
  }) => (
    <a href={href} className={className} aria-label={ariaLabel}>
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

const baseUser = {
  uid: "alice",
  email: "alice@example.com",
  displayName: "Alice Example",
  photoURL: null,
};

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

  it("renders the brand mark, nav, Subjects header, SubjectsNav, and children", () => {
    render(
      withIntl(
        <AppShell user={baseUser}>
          <div data-testid="content">Hello</div>
        </AppShell>,
      ),
    );
    expect(screen.getByLabelText("Shomery home")).toBeInTheDocument();
    expect(screen.getByText("Inbox")).toBeInTheDocument();
    expect(screen.getByText("Subjects")).toBeInTheDocument();
    expect(screen.getByTestId("subjects-nav")).toHaveTextContent("alice");
    expect(screen.getByTestId("content")).toBeInTheDocument();
  });

  it("renders the user chip with displayName and email", () => {
    render(
      withIntl(
        <AppShell user={baseUser}>
          <div />
        </AppShell>,
      ),
    );
    expect(screen.getByText("Alice Example")).toBeInTheDocument();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
  });

  it("falls back to email-only when displayName is missing", () => {
    render(
      withIntl(
        <AppShell user={{ ...baseUser, displayName: null }}>
          <div />
        </AppShell>,
      ),
    );
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.queryByText("Alice Example")).not.toBeInTheDocument();
  });

  it("renders avatar image when photoURL is present", () => {
    const { container } = render(
      withIntl(
        <AppShell
          user={{ ...baseUser, photoURL: "https://example.com/a.jpg" }}
        >
          <div />
        </AppShell>,
      ),
    );
    const img = container.querySelector("img");
    expect(img).toHaveAttribute("src", "https://example.com/a.jpg");
  });

  it("invokes signOutOfShomery when the sign-out button is clicked", async () => {
    render(
      withIntl(
        <AppShell user={baseUser}>
          <div />
        </AppShell>,
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOutOfShomery).toHaveBeenCalled();
  });

  it("marks the Inbox link active when pathname is /feed", () => {
    usePathnameMock.mockReturnValue("/feed");
    render(
      withIntl(
        <AppShell user={baseUser}>
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
        <AppShell user={baseUser}>
          <div />
        </AppShell>,
      ),
    );
    const inbox = screen.getByText("Inbox").closest("a")!;
    expect(inbox.className).not.toContain("bg-brand-tint");
  });
});
