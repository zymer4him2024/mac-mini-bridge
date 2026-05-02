"use client";

import type { ReactNode } from "react";

import { Inbox, LogOut, Settings as SettingsIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/routing";
import { signOutOfShomery } from "@/lib/firebase/auth";

import { SubjectsNav } from "./subjects-nav";

interface AppShellUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
}

function NavLink({
  href,
  active,
  icon: Icon,
  children,
}: {
  href: string;
  active: boolean;
  icon: typeof Inbox;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-md border-l-2 px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? "border-brand bg-brand-tint text-ink"
          : "border-transparent text-soft hover:bg-soft/5 hover:text-ink"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{children}</span>
    </Link>
  );
}

function BrandMark() {
  const t = useTranslations("nav");
  return (
    <Link
      href="/feed"
      className="flex items-center gap-2 px-1.5 py-1 text-ink hover:opacity-80"
      aria-label={t("brandHome")}
    >
      <span
        aria-hidden="true"
        className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-sm font-bold leading-none text-paper"
      >
        {t("brandMonogram")}
      </span>
      <span className="text-base font-bold tracking-tight">{t("brand")}</span>
    </Link>
  );
}

function UserChip({
  user,
  signOutLabel,
}: {
  user: AppShellUser;
  signOutLabel: string;
}) {
  const initial = (user.displayName || user.email || "?").charAt(0).toUpperCase();
  const primary = user.displayName || user.email || "";
  const secondary = user.displayName ? user.email : null;

  return (
    <div className="flex items-center gap-3 rounded-md px-2 py-2">
      {user.photoURL ? (
        // eslint-disable-next-line @next/next/no-img-element -- external Google avatar; static export disables next/image
        <img
          src={user.photoURL}
          alt=""
          className="h-8 w-8 shrink-0 rounded-full"
          referrerPolicy="no-referrer"
        />
      ) : (
        <span
          aria-hidden="true"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-tint text-sm font-bold text-ink"
        >
          {initial}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink">{primary}</p>
        {secondary ? (
          <p className="truncate text-xs text-soft">{secondary}</p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => signOutOfShomery()}
        aria-label={signOutLabel}
        className="rounded-md p-1.5 text-soft hover:bg-soft/5 hover:text-ink"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export function AppShell({
  user,
  children,
}: {
  user: AppShellUser;
  children: ReactNode;
}) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="flex flex-col border-b border-soft/10 bg-paper md:h-screen md:w-64 md:shrink-0 md:border-b-0 md:border-r">
        <div className="border-b border-soft/10 p-4">
          <BrandMark />
        </div>

        <div className="flex-1 overflow-y-auto p-3">
          <nav className="space-y-0.5" aria-label="Primary">
            <NavLink
              href="/feed"
              active={pathname === "/feed"}
              icon={Inbox}
            >
              {t("inbox")}
            </NavLink>
            <NavLink
              href="/settings"
              active={pathname === "/settings"}
              icon={SettingsIcon}
            >
              {t("settings")}
            </NavLink>
          </nav>

          <div className="mt-6">
            <p className="px-3 text-xs font-bold uppercase tracking-wider text-soft">
              {t("subjectsHeader")}
            </p>
            <div className="mt-2">
              <SubjectsNav uid={user.uid} />
            </div>
          </div>
        </div>

        <div className="border-t border-soft/10 p-3">
          <UserChip user={user} signOutLabel={t("signOut")} />
        </div>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
