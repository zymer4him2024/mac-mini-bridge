import type { ReactNode } from "react";

import type { Folder, Group } from "@shomery/shared-types";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Timestamp } from "firebase/firestore";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import enMessages from "../../../messages/en.json";

const createGroup = vi.fn();
const renameGroup = vi.fn();
const setMembersFn = vi.fn();
const deleteGroup = vi.fn();
let groupsValue: Group[] | null = [];

vi.mock("@/lib/use-groups", () => ({
  useGroups: () => ({
    groups: groupsValue,
    createGroup,
    renameGroup,
    setMembers: setMembersFn,
    deleteGroup,
  }),
}));

import { GroupsEditor } from "@/components/settings/groups-editor";

function withIntl(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages} timeZone="UTC">
      {node}
    </NextIntlClientProvider>
  );
}

const ts = () => Timestamp.fromDate(new Date());

function makeFolder(subject: string, slug: string): Folder {
  return {
    subject,
    subjectSlug: slug,
    folderPath: `/${slug}`,
    pdfCount: 1,
    hasSummaryCsv: false,
    createdAt: ts(),
    updatedAt: ts(),
  };
}

function makeGroup(
  groupId: string,
  name: string,
  subjectSlugs: string[],
): Group {
  return { groupId, name, subjectSlugs, createdAt: ts(), updatedAt: ts() };
}

describe("GroupsEditor", () => {
  beforeEach(() => {
    createGroup.mockReset().mockResolvedValue("new-id");
    renameGroup.mockReset().mockResolvedValue(undefined);
    setMembersFn.mockReset().mockResolvedValue(undefined);
    deleteGroup.mockReset().mockResolvedValue(undefined);
    groupsValue = [];
  });

  it("renders the empty state when there are no groups", () => {
    groupsValue = [];
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    expect(
      screen.getByText(
        "You don't have any groups yet. Create one to bundle related subjects.",
      ),
    ).toBeInTheDocument();
  });

  it("renders a loading state while groups is null", () => {
    groupsValue = null;
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("creates a new group on click", async () => {
    const user = userEvent.setup();
    groupsValue = [];
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    await user.type(screen.getByLabelText("New group name"), "Acme");
    await user.click(screen.getByRole("button", { name: "Add group" }));
    expect(createGroup).toHaveBeenCalledWith("Acme");
  });

  it("disables the create button when the name is empty", () => {
    groupsValue = [];
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    expect(screen.getByRole("button", { name: "Add group" })).toBeDisabled();
  });

  it("lists existing groups with member count", () => {
    groupsValue = [makeGroup("g1", "Clients", ["acme", "okrs"])];
    render(
      withIntl(
        <GroupsEditor
          uid="alice"
          folders={[
            makeFolder("Acme", "acme"),
            makeFolder("OKRs", "okrs"),
          ]}
        />,
      ),
    );
    expect(screen.getByText("Clients")).toBeInTheDocument();
    expect(screen.getByText("2 subjects")).toBeInTheDocument();
  });

  it("opens the members editor and saves selected slugs", async () => {
    const user = userEvent.setup();
    groupsValue = [makeGroup("g1", "Clients", ["acme"])];
    render(
      withIntl(
        <GroupsEditor
          uid="alice"
          folders={[
            makeFolder("Acme", "acme"),
            makeFolder("OKRs", "okrs"),
          ]}
        />,
      ),
    );
    await user.click(screen.getByRole("button", { name: "Edit members" }));
    await user.click(screen.getByLabelText("OKRs"));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(setMembersFn).toHaveBeenCalledTimes(1);
    const [groupId, slugs] = setMembersFn.mock.calls[0];
    expect(groupId).toBe("g1");
    expect(new Set(slugs)).toEqual(new Set(["acme", "okrs"]));
  });

  it("requires the typed name to confirm a delete", async () => {
    const user = userEvent.setup();
    groupsValue = [makeGroup("g1", "Clients", [])];
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    await user.click(screen.getByRole("button", { name: "Delete" }));
    const confirmBtn = screen.getByRole("button", { name: "Delete group" });
    expect(confirmBtn).toBeDisabled();
    await user.type(screen.getByLabelText("Confirmation phrase"), "Clients");
    expect(confirmBtn).toBeEnabled();
    await user.click(confirmBtn);
    expect(deleteGroup).toHaveBeenCalledWith("g1");
  });

  it("renames a group", async () => {
    const user = userEvent.setup();
    groupsValue = [makeGroup("g1", "Clients", [])];
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    // Click the group name to enter rename mode.
    await user.click(screen.getByRole("button", { name: /^Clients/ }));
    const input = screen.getByLabelText("Group name");
    await user.clear(input);
    await user.type(input, "VIP Clients");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(renameGroup).toHaveBeenCalledWith("g1", "VIP Clients");
  });

  it("shows error UI when create fails", async () => {
    const user = userEvent.setup();
    createGroup.mockRejectedValueOnce(new Error("boom"));
    // Silence the expected console.error
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    groupsValue = [];
    render(withIntl(<GroupsEditor uid="alice" folders={[]} />));
    await user.type(screen.getByLabelText("New group name"), "Acme");
    await act(async () => {
      await user.click(screen.getByRole("button", { name: "Add group" }));
    });
    expect(
      screen.getByText("We couldn't save your changes. Please try again."),
    ).toBeInTheDocument();
    errSpy.mockRestore();
  });
});
