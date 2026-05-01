"use client";

import type { ReactNode } from "react";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/routing";
import { signOutOfShomery } from "@/lib/firebase/auth";

import { SubjectsNav } from "./subjects-nav";

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center rounded border-l-2 px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? "border-brand bg-brand-tint text-ink"
          : "border-transparent text-soft hover:bg-soft/5 hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

export function AppShell({
  uid,
  children,
}: {
  uid: string;
  children: ReactNode;
}) {
  const t = useTranslations("nav");
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-soft/10 bg-paper p-4 md:w-64 md:shrink-0 md:border-b-0 md:border-r">
        <div className="flex items-center justify-between md:block">
          <nav className="space-y-0.5">
            <NavLink href="/feed" active={pathname === "/feed"}>
              {t("inbox")}
            </NavLink>
            <NavLink href="/settings" active={pathname === "/settings"}>
              {t("settings")}
            </NavLink>
          </nav>
          <button
            type="button"
            onClick={() => signOutOfShomery()}
            className="px-3 py-2 text-sm text-soft hover:text-ink md:hidden"
          >
            {t("signOut")}
          </button>
        </div>

        <div className="mt-6">
          <p className="px-3 text-xs font-bold uppercase tracking-wide text-soft">
            {t("subjectsHeader")}
          </p>
          <div className="mt-2">
            <SubjectsNav uid={uid} />
          </div>
        </div>

        <button
          type="button"
          onClick={() => signOutOfShomery()}
          className="mt-8 hidden px-3 py-2 text-sm text-soft hover:text-ink md:block"
        >
          {t("signOut")}
        </button>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
