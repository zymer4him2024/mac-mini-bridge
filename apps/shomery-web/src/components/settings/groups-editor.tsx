"use client";

import { useMemo, useState } from "react";

import type { Folder, Group } from "@shomery/shared-types";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { useGroups } from "@/lib/use-groups";

type RowMode = "members" | "rename" | "delete" | null;
type SaveState = "idle" | "saving" | "error";

const NAME_MAX = 50;

export function GroupsEditor({
  uid,
  folders,
}: {
  uid: string;
  folders: Folder[];
}) {
  const t = useTranslations("settings.groups");
  const { groups, createGroup, renameGroup, setMembers, deleteGroup } =
    useGroups(uid);

  const [createDraft, setCreateDraft] = useState("");
  const [createState, setCreateState] = useState<SaveState>("idle");
  const [activeRow, setActiveRow] = useState<{
    groupId: string;
    mode: RowMode;
  }>({ groupId: "", mode: null });
  const [renameDraft, setRenameDraft] = useState("");
  const [memberDraft, setMemberDraft] = useState<Set<string>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [rowState, setRowState] = useState<SaveState>("idle");

  const subjectCatalog = useMemo(
    () =>
      folders.map((f) => ({
        slug: f.subjectSlug,
        subject: f.subject,
      })),
    [folders],
  );

  const trimmedCreate = createDraft.trim();
  const createInvalid =
    trimmedCreate.length === 0 || trimmedCreate.length > NAME_MAX;

  const onCreate = async () => {
    if (createInvalid) return;
    setCreateState("saving");
    try {
      await createGroup(trimmedCreate);
      setCreateDraft("");
      setCreateState("idle");
    } catch (err) {
      console.error("Failed to create group", err);
      setCreateState("error");
    }
  };

  const openRow = (groupId: string, mode: RowMode, group?: Group) => {
    setActiveRow({ groupId, mode });
    setRowState("idle");
    if (mode === "rename" && group) setRenameDraft(group.name);
    if (mode === "members" && group) {
      setMemberDraft(new Set(group.subjectSlugs));
    }
    if (mode === "delete") setDeleteConfirm("");
  };

  const closeRow = () => {
    setActiveRow({ groupId: "", mode: null });
    setRowState("idle");
  };

  const onRenameSave = async (groupId: string) => {
    const name = renameDraft.trim();
    if (name.length === 0 || name.length > NAME_MAX) return;
    setRowState("saving");
    try {
      await renameGroup(groupId, name);
      closeRow();
    } catch (err) {
      console.error("Failed to rename group", err);
      setRowState("error");
    }
  };

  const onMembersSave = async (groupId: string) => {
    setRowState("saving");
    try {
      await setMembers(groupId, Array.from(memberDraft));
      closeRow();
    } catch (err) {
      console.error("Failed to update group members", err);
      setRowState("error");
    }
  };

  const onDeleteConfirm = async (groupId: string, name: string) => {
    if (deleteConfirm.trim() !== name) return;
    setRowState("saving");
    try {
      await deleteGroup(groupId);
      closeRow();
    } catch (err) {
      console.error("Failed to delete group", err);
      setRowState("error");
    }
  };

  const toggleMember = (slug: string) => {
    setMemberDraft((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  };

  return (
    <section
      aria-labelledby="groups-heading"
      className="border-l-accent border-brand bg-paper py-6 pl-6 pr-4 shadow-sm"
    >
      <h2 id="groups-heading" className="text-base font-bold text-ink">
        {t("label")}
      </h2>
      <p className="mt-1 text-sm text-soft">{t("helpText")}</p>

      {groups === null ? (
        <p className="mt-4 text-sm text-soft">{t("loading")}</p>
      ) : groups.length === 0 ? (
        <p className="mt-4 text-sm text-soft">{t("empty")}</p>
      ) : (
        <ul className="mt-4 space-y-2">
          {groups.map((group) => {
            const isActive = activeRow.groupId === group.groupId;
            const memberCount = group.subjectSlugs.length;
            return (
              <li
                key={group.groupId}
                className="rounded border border-soft/10 bg-paper"
              >
                <div className="flex items-center justify-between gap-3 px-3 py-2">
                  {isActive && activeRow.mode === "rename" ? (
                    <div className="flex flex-1 items-center gap-2">
                      <input
                        type="text"
                        value={renameDraft}
                        onChange={(e) => setRenameDraft(e.target.value)}
                        aria-label={t("nameLabel")}
                        maxLength={NAME_MAX}
                        className="flex-1 rounded border border-soft/20 bg-paper px-2 py-1 text-sm text-ink focus:border-brand focus:outline-none"
                      />
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => onRenameSave(group.groupId)}
                        disabled={
                          rowState === "saving" ||
                          renameDraft.trim().length === 0 ||
                          renameDraft.trim().length > NAME_MAX
                        }
                      >
                        {rowState === "saving"
                          ? t("savingAction")
                          : t("saveAction")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={closeRow}
                        disabled={rowState === "saving"}
                      >
                        {t("cancelAction")}
                      </Button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => openRow(group.groupId, "rename", group)}
                        className="flex flex-1 items-center gap-2 truncate text-left text-sm font-bold text-ink hover:text-brand"
                      >
                        {group.name}
                        <span className="text-xs font-normal text-soft">
                          {t("memberCount", { count: memberCount })}
                        </span>
                      </button>
                      <div className="flex shrink-0 items-center gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            openRow(group.groupId, "members", group)
                          }
                        >
                          {t("editMembersCta")}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => openRow(group.groupId, "delete")}
                          className="text-warn hover:text-warn"
                        >
                          {t("deleteCta")}
                        </Button>
                      </div>
                    </>
                  )}
                </div>

                {isActive && activeRow.mode === "members" ? (
                  <div className="border-t border-soft/10 px-3 py-3">
                    <p className="text-xs text-soft">{t("membersHelp")}</p>
                    {subjectCatalog.length === 0 ? (
                      <p className="mt-3 text-sm text-soft">
                        {t("noSubjectsAvailable")}
                      </p>
                    ) : (
                      <ul className="mt-3 max-h-64 space-y-1 overflow-y-auto">
                        {subjectCatalog.map((s) => {
                          const checked = memberDraft.has(s.slug);
                          const inputId = `group-${group.groupId}-member-${s.slug}`;
                          return (
                            <li key={s.slug}>
                              <label
                                htmlFor={inputId}
                                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-ink hover:bg-soft/5"
                              >
                                <input
                                  id={inputId}
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => toggleMember(s.slug)}
                                  className="h-4 w-4 accent-brand"
                                />
                                <span className="truncate">{s.subject}</span>
                              </label>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                    <div className="mt-3 flex items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => onMembersSave(group.groupId)}
                        disabled={rowState === "saving"}
                      >
                        {rowState === "saving"
                          ? t("savingAction")
                          : t("saveAction")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={closeRow}
                        disabled={rowState === "saving"}
                      >
                        {t("cancelAction")}
                      </Button>
                      {rowState === "error" ? (
                        <span role="alert" className="text-xs text-warn">
                          {t("saveError")}
                        </span>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {isActive && activeRow.mode === "delete" ? (
                  <div className="border-t border-warn/30 bg-warn/5 px-3 py-3">
                    <p className="text-sm text-ink">
                      {t("confirmDeletePrompt", {
                        name: group.name,
                      })}
                    </p>
                    <input
                      type="text"
                      value={deleteConfirm}
                      onChange={(e) => setDeleteConfirm(e.target.value)}
                      aria-label={t("confirmInputLabel")}
                      placeholder={group.name}
                      className="mt-3 w-full rounded border border-soft/20 bg-paper px-2 py-1 text-sm text-ink placeholder:text-soft focus:border-warn focus:outline-none"
                      disabled={rowState === "saving"}
                    />
                    <div className="mt-3 flex items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        onClick={() =>
                          onDeleteConfirm(group.groupId, group.name)
                        }
                        disabled={
                          deleteConfirm.trim() !== group.name ||
                          rowState === "saving"
                        }
                      >
                        {rowState === "saving"
                          ? t("deletingAction")
                          : t("confirmDeleteCta")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={closeRow}
                        disabled={rowState === "saving"}
                      >
                        {t("cancelAction")}
                      </Button>
                      {rowState === "error" ? (
                        <span role="alert" className="text-xs text-warn">
                          {t("saveError")}
                        </span>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-6 flex items-start gap-2">
        <input
          type="text"
          value={createDraft}
          onChange={(e) => {
            setCreateDraft(e.target.value);
            if (createState !== "idle") setCreateState("idle");
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onCreate();
            }
          }}
          placeholder={t("newGroupPlaceholder")}
          aria-label={t("newGroupAriaLabel")}
          maxLength={NAME_MAX}
          className="flex-1 rounded border border-soft/20 bg-paper px-3 py-2 text-sm text-ink placeholder:text-soft focus:border-brand focus:outline-none"
        />
        <Button
          type="button"
          onClick={onCreate}
          disabled={createInvalid || createState === "saving"}
        >
          {createState === "saving"
            ? t("savingAction")
            : t("newGroupCta")}
        </Button>
      </div>

      {createState === "error" ? (
        <p role="alert" className="mt-2 text-sm text-warn">
          {t("saveError")}
        </p>
      ) : null}
    </section>
  );
}
