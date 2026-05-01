#!/usr/bin/env python3
"""Verify the pilot UI/UX hardening fixes are present and correctly wired.

Static-only checks — does not execute Next.js, only inspects files.
Run: python3 test_ui_pilot.py
Exits 1 on any failure.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PORTAL = Path(__file__).resolve().parent / "ui-platform/apps/email2ppt-portal/src"


@dataclass
class Results:
    passed: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)

    def ok(self, label: str) -> None:
        self.passed += 1
        print(f"  PASS  {label}")

    def bad(self, label: str, detail: str = "") -> None:
        self.failed += 1
        msg = f"{label}: {detail}" if detail else label
        self.failures.append(msg)
        print(f"  FAIL  {msg}")


def header(title: str) -> None:
    print(f"\n=== {title} ===")


def must_read(path: Path, r: Results, label: str) -> str | None:
    if not path.exists():
        r.bad(label, f"missing file {path}")
        return None
    return path.read_text(encoding="utf-8")


# --- Fix 1: SENDERS step in onboarding wizard ---


def test_fix1_senders_step(r: Results) -> None:
    header("Fix 1: SENDERS step in onboarding wizard")

    senders_step = PORTAL / "components/onboard/senders-step.tsx"
    text = must_read(senders_step, r, "senders-step.tsx exists")
    if text:
        r.ok("senders-step.tsx exists")
        for needle, label in [
            ('"use client"', "senders-step is a client component"),
            ("priorityWatchSenders", "writes to priorityWatchSenders"),
            ("setDoc", "uses setDoc"),
            ("merge: true", "uses merge:true"),
            ("EMAIL_PATTERN", "validates email format"),
            ("DOMAIN_PATTERN", "validates domain format"),
        ]:
            if needle in text:
                r.ok(label)
            else:
                r.bad(label, f"missing token {needle!r}")

    onboard = PORTAL / "app/onboard/page.tsx"
    text = must_read(onboard, r, "onboard/page.tsx exists")
    if text:
        for needle, label in [
            ('"SENDERS"', "STEP_VALUES contains SENDERS"),
            ("SendersStep", "SendersStep component imported/used"),
            ("totalSteps={4}", "wizard advertises 4 total steps"),
        ]:
            if needle in text:
                r.ok(label)
            else:
                r.bad(label, f"missing token {needle!r}")

        # SENDERS must come AFTER TEST_PENDING and BEFORE DONE
        if re.search(r"TEST_PENDING.*SENDERS.*DONE", text, re.DOTALL):
            r.ok("STEP_VALUES order: TEST_PENDING -> SENDERS -> DONE")
        else:
            r.bad("STEP_VALUES order", "expected TEST_PENDING then SENDERS then DONE")


# --- Fix 2: Dashboard banner fires when senders == 0 ---


def test_fix2_dashboard_banner(r: Results) -> None:
    header("Fix 2: Dashboard banner when no priority senders")

    page = PORTAL / "app/page.tsx"
    text = must_read(page, r, "app/page.tsx exists")
    if text:
        for needle, label in [
            ("needsSenders", "needsSenders predicate exists"),
            ("senderCount === 0", "predicate triggers on senderCount === 0"),
            ("border-warning", "uses warning token for banner border"),
            ("/senders", "links to /senders CTA"),
        ]:
            if needle in text:
                r.ok(label)
            else:
                r.bad(label, f"missing token {needle!r}")


# --- Fix 3: DONE screen copy + quick-link buttons ---


def test_fix3_done_screen(r: Results) -> None:
    header("Fix 3: DONE screen copy + quick-link buttons")

    onboard = PORTAL / "app/onboard/page.tsx"
    text = must_read(onboard, r, "onboard/page.tsx exists")
    if text:
        for needle, label in [
            ("every 5 minutes", "DONE copy mentions 5-minute cadence"),
            ('href="/"', "Go to dashboard button"),
            ('href="/senders"', "Add more senders button"),
            ('href="/settings"', "Tune summary style button"),
        ]:
            if needle in text:
                r.ok(label)
            else:
                r.bad(label, f"missing token {needle!r}")


# --- Fix 4: error.tsx + loading.tsx for every route ---


REQUIRED_BOUNDARY_DIRS = [
    "app",
    "app/senders",
    "app/folders",
    "app/folders/[slug]",
    "app/activity",
    "app/settings",
    "app/admin",
    "app/admin/activity",
    "app/leads",
]


def test_fix4_boundaries(r: Results) -> None:
    header("Fix 4: loading.tsx + error.tsx on every route")

    for rel in REQUIRED_BOUNDARY_DIRS:
        loading = PORTAL / rel / "loading.tsx"
        error = PORTAL / rel / "error.tsx"

        if loading.exists():
            r.ok(f"{rel}/loading.tsx exists")
        else:
            r.bad(f"{rel}/loading.tsx exists", "missing")

        text = must_read(error, r, f"{rel}/error.tsx exists")
        if text is None:
            continue

        # Strict: first non-empty line must be "use client" directive
        first_line = next(
            (ln.strip() for ln in text.splitlines() if ln.strip()),
            "",
        )
        if first_line in ('"use client";', "'use client';"):
            r.ok(f"{rel}/error.tsx starts with 'use client' directive")
        else:
            r.bad(
                f"{rel}/error.tsx 'use client' directive",
                f"first line was {first_line!r}",
            )

        for needle, label in [
            ("reset", f"{rel}/error.tsx wires reset()"),
            ("error.message", f"{rel}/error.tsx renders error.message"),
        ]:
            if needle in text:
                r.ok(label)
            else:
                r.bad(label, f"missing token {needle!r}")


# --- Fix 5: Settings tabs trimmed ---


def test_fix5_settings_tabs(r: Results) -> None:
    header("Fix 5: Settings tabs trimmed")

    settings = PORTAL / "app/settings/page.tsx"
    text = must_read(settings, r, "app/settings/page.tsx exists")
    if text is None:
        return

    # The tabs are objects like { id: "watcher", ... }. Look for id strings.
    for forbidden in ('id: "digest"', 'id: "model"'):
        if forbidden in text:
            r.bad(f"forbidden tab present: {forbidden}")
        else:
            r.ok(f"forbidden tab absent: {forbidden}")

    # And lucide imports for those tabs should be gone
    for forbidden in ("FileText", "Brain"):
        if re.search(rf"\b{forbidden}\b", text):
            r.bad(f"{forbidden} import not removed")
        else:
            r.ok(f"{forbidden} import removed")

    # Must still have the real tabs
    for kept in ('id: "watcher"', 'id: "gmail"', 'id: "telegram"', 'id: "summary"'):
        if kept in text:
            r.ok(f"kept tab present: {kept}")
        else:
            r.bad(f"kept tab missing: {kept}")


# --- Fix 6: Telegram link timeout ---


def test_fix6_telegram_timeout(r: Results) -> None:
    header("Fix 6: Telegram LINKING 5-minute timeout")

    linking = PORTAL / "components/onboard/linking-step.tsx"
    text = must_read(linking, r, "linking-step.tsx exists")
    if text is None:
        return

    for needle, label in [
        ("setTimeout", "uses setTimeout"),
        ("5 * 60 * 1000", "timeout is 5 minutes"),
        ("clearTimeout", "cleans up timer"),
        ("retryKey", "remounts QuickLinkSetup with retryKey"),
    ]:
        if needle in text:
            r.ok(label)
        else:
            r.bad(label, f"missing token {needle!r}")


def main() -> int:
    if not PORTAL.exists():
        print(f"FATAL: portal src not found at {PORTAL}", file=sys.stderr)
        return 2

    r = Results()
    test_fix1_senders_step(r)
    test_fix2_dashboard_banner(r)
    test_fix3_done_screen(r)
    test_fix4_boundaries(r)
    test_fix5_settings_tabs(r)
    test_fix6_telegram_timeout(r)

    print(f"\n=== Summary ===\n  {r.passed} PASS  {r.failed} FAIL")
    if r.failed:
        print("\nFailures:")
        for f in r.failures:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
