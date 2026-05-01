import type { ReactNode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const buildExportMock = vi.fn();
const downloadExportMock = vi.fn();
const callDeleteAccountMock = vi.fn();
const signOutMock = vi.fn();
const routerReplaceMock = vi.fn();

vi.mock("@/lib/account-export", () => ({
  buildAccountExport: (...args: unknown[]) => buildExportMock(...args),
  downloadExport: (...args: unknown[]) => downloadExportMock(...args),
}));

vi.mock("@/lib/account-delete", () => ({
  callDeleteAccount: (...args: unknown[]) => callDeleteAccountMock(...args),
}));

vi.mock("@/lib/firebase/auth", () => ({
  signOutOfShomery: (...args: unknown[]) => signOutMock(...args),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ replace: routerReplaceMock }),
}));

import { PrivacyDataEditor } from "@/components/settings/privacy-data-editor";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

describe("PrivacyDataEditor", () => {
  beforeEach(() => {
    buildExportMock.mockReset();
    downloadExportMock.mockReset();
    callDeleteAccountMock.mockReset();
    signOutMock.mockReset();
    routerReplaceMock.mockReset();
  });

  it("renders the export and delete sections", () => {
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    expect(
      screen.getByRole("heading", { name: "Export my data" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Delete my account" }),
    ).toBeInTheDocument();
  });

  it("downloads the export when the user clicks the export button", async () => {
    buildExportMock.mockResolvedValue({ uid: "alice" });
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    await userEvent.click(
      screen.getByRole("button", { name: "Download export" }),
    );
    await waitFor(() => expect(buildExportMock).toHaveBeenCalledOnce());
    expect(downloadExportMock).toHaveBeenCalledWith({ uid: "alice" });
    expect(await screen.findByText("Downloaded.")).toBeInTheDocument();
  });

  it("shows an inline error when the export build fails", async () => {
    buildExportMock.mockRejectedValueOnce(new Error("boom"));
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    await userEvent.click(
      screen.getByRole("button", { name: "Download export" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't build your export. Please try again.",
    );
  });

  it("requires the confirmation phrase before enabling permanent delete", async () => {
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    await userEvent.click(
      screen.getByRole("button", { name: "Delete my account" }),
    );
    const confirm = screen.getByRole("button", { name: "Permanently delete" });
    expect(confirm).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText("Confirmation phrase"),
      "DELETE",
    );
    expect(
      screen.getByRole("button", { name: "Permanently delete" }),
    ).toBeEnabled();
  });

  it("calls deleteAccount, signs out, and routes to /sign-in on success", async () => {
    callDeleteAccountMock.mockResolvedValue(undefined);
    signOutMock.mockResolvedValue(undefined);
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    await userEvent.click(
      screen.getByRole("button", { name: "Delete my account" }),
    );
    await userEvent.type(
      screen.getByLabelText("Confirmation phrase"),
      "DELETE",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Permanently delete" }),
    );
    await waitFor(() =>
      expect(callDeleteAccountMock).toHaveBeenCalledOnce(),
    );
    expect(signOutMock).toHaveBeenCalledOnce();
    expect(routerReplaceMock).toHaveBeenCalledWith("/sign-in");
  });

  it("shows an inline error when delete fails and keeps the user signed in", async () => {
    callDeleteAccountMock.mockRejectedValueOnce(new Error("rpc-failed"));
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    await userEvent.click(
      screen.getByRole("button", { name: "Delete my account" }),
    );
    await userEvent.type(
      screen.getByLabelText("Confirmation phrase"),
      "DELETE",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Permanently delete" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't delete your account. Please try again.",
    );
    expect(signOutMock).not.toHaveBeenCalled();
    expect(routerReplaceMock).not.toHaveBeenCalled();
  });

  it("cancels the confirmation panel and clears the typed phrase", async () => {
    render(withIntl(<PrivacyDataEditor uid="alice" />));
    await userEvent.click(
      screen.getByRole("button", { name: "Delete my account" }),
    );
    await userEvent.type(
      screen.getByLabelText("Confirmation phrase"),
      "DELETE",
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.queryByLabelText("Confirmation phrase"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete my account" }),
    ).toBeInTheDocument();
  });
});
