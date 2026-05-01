import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const setDocMock = vi.fn();

vi.mock("firebase/firestore", async () => {
  const actual = await vi.importActual<typeof import("firebase/firestore")>(
    "firebase/firestore",
  );
  return {
    ...actual,
    doc: () => ({}),
    setDoc: (...args: unknown[]) => setDocMock(...args),
  };
});

vi.mock("@/lib/firebase/client", () => ({
  getFirebaseDb: () => ({}),
}));

import { WatchedSendersEditor } from "@/components/settings/watched-senders-editor";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("WatchedSendersEditor", () => {
  beforeEach(() => {
    setDocMock.mockReset();
    setDocMock.mockResolvedValue(undefined);
  });

  it("renders the empty state when there are no entries", () => {
    render(withIntl(<WatchedSendersEditor uid="alice" initial={[]} />));
    expect(
      screen.getByText("No watched senders yet. Add one below."),
    ).toBeInTheDocument();
  });

  it("renders one row per existing entry", () => {
    render(
      withIntl(
        <WatchedSendersEditor
          uid="alice"
          initial={["alice@example.com", "@acme.com"]}
        />,
      ),
    );
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("@acme.com")).toBeInTheDocument();
  });

  it("adds a new entry and clears the input", async () => {
    render(withIntl(<WatchedSendersEditor uid="alice" initial={[]} />));
    const input = screen.getByPlaceholderText("alice@example.com or @acme.com");
    await userEvent.type(input, "alice@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("shows an inline validation error for an invalid format", async () => {
    render(withIntl(<WatchedSendersEditor uid="alice" initial={[]} />));
    await userEvent.type(
      screen.getByPlaceholderText("alice@example.com or @acme.com"),
      "not an email",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Use an email address or a domain like acme.com or @acme.com.",
    );
  });

  it("rejects a duplicate entry case-insensitively", async () => {
    render(
      withIntl(
        <WatchedSendersEditor uid="alice" initial={["alice@example.com"]} />,
      ),
    );
    await userEvent.type(
      screen.getByPlaceholderText("alice@example.com or @acme.com"),
      "ALICE@example.com",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ALICE@example.com is already on the list.",
    );
  });

  it("removes an entry when its remove button is clicked", async () => {
    render(
      withIntl(
        <WatchedSendersEditor uid="alice" initial={["alice@example.com"]} />,
      ),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Remove alice@example.com" }),
    );
    expect(screen.queryByText("alice@example.com")).not.toBeInTheDocument();
  });

  it("disables save when the list is unchanged", () => {
    render(
      withIntl(
        <WatchedSendersEditor uid="alice" initial={["alice@example.com"]} />,
      ),
    );
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("calls setDoc with the new list and shows a saved confirmation", async () => {
    render(withIntl(<WatchedSendersEditor uid="alice" initial={[]} />));
    await userEvent.type(
      screen.getByPlaceholderText("alice@example.com or @acme.com"),
      "alice@example.com",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(setDocMock).toHaveBeenCalledOnce());
    expect(setDocMock).toHaveBeenCalledWith(
      expect.anything(),
      { priorityWatchSenders: ["alice@example.com"] },
      { merge: true },
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("shows an inline error when setDoc rejects", async () => {
    setDocMock.mockRejectedValueOnce(new Error("permission-denied"));
    render(withIntl(<WatchedSendersEditor uid="alice" initial={[]} />));
    await userEvent.type(
      screen.getByPlaceholderText("alice@example.com or @acme.com"),
      "alice@example.com",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't save your changes. Please try again.",
    );
  });
});
