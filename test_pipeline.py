"""End-to-end check for the email2ppt pipeline + security + structure.

Run: python test_pipeline.py

No network or Firestore access is required — upsert_lead behavior is verified
against a MagicMock that simulates Firestore. The script is idempotent; rerun
after every change to the lead tracker, watcher, portal /leads page, or
firestore.rules.

Exit code: 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import ast
import re
import sys
from email.utils import parseaddr
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parent
PY_FILES = sorted(p for p in REPO.glob("*.py") if "__pycache__" not in str(p))

_PASS = 0
_FAIL = 0


def _check(name: str, ok: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    print(f"{'[PASS]' if ok else '[FAIL]'} {name}{f' — {detail}' if detail else ''}")
    if ok:
        _PASS += 1
    else:
        _FAIL += 1


def _section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------------------
# 1. Pipeline (lead tracker semantics, parseaddr sanity)
# ---------------------------------------------------------------------------


def test_lead_id_determinism() -> None:
    from firestore_leads import _lead_id

    a = _lead_id("Alice@Acme.com  ", "investor-update-q3")
    b = _lead_id("alice@acme.com", "investor-update-q3")
    _check("lead_id is case-insensitive and trimmed", a == b)
    _check(
        "lead_id is 16-char lowercase hex",
        len(a) == 16 and re.fullmatch(r"[0-9a-f]{16}", a) is not None,
        a,
    )
    _check(
        "different subject -> different lead_id",
        _lead_id("alice@acme.com", "subject-a")
        != _lead_id("alice@acme.com", "subject-b"),
    )
    _check(
        "different sender -> different lead_id",
        _lead_id("alice@acme.com", "s") != _lead_id("bob@acme.com", "s"),
    )


def _make_db(existing: dict | None) -> tuple[MagicMock, MagicMock]:
    """Returns (db_mock, ref_mock). ref_mock.set captures the upsert payload."""
    db = MagicMock()
    snap = MagicMock()
    snap.exists = existing is not None
    snap.to_dict.return_value = existing or {}
    ref = db.collection.return_value.document.return_value.collection.return_value.document.return_value
    ref.get.return_value = snap
    return db, ref


def test_upsert_lead_first_write() -> None:
    from firestore_leads import upsert_lead

    db, ref = _make_db(existing=None)
    upsert_lead(
        db,
        "uid-1",
        sender_email="alice@acme.com",
        sender_name="Alice Chen",
        subject="Hello",
        subject_slug="hello",
        urgency="med",
        pdf_filename="x.pdf",
        suggested_response="Reply Friday",
    )

    ref.set.assert_called_once()
    payload = ref.set.call_args.args[0]
    kwargs = ref.set.call_args.kwargs

    _check("first write uses merge=True", kwargs.get("merge") is True)
    _check("first write sets status='new'", payload.get("status") == "new")
    _check("first write sets firstSeenAt", "firstSeenAt" in payload)
    _check("first write sets createdAt", "createdAt" in payload)
    _check("first write interactionCount=1", payload.get("interactionCount") == 1)
    _check(
        "first write normalizes senderEmail to lowercase",
        payload.get("senderEmail") == "alice@acme.com",
    )


def test_upsert_lead_preserves_user_status() -> None:
    """Highest-impact regression: subsequent writes must not clobber status."""
    from firestore_leads import upsert_lead

    db, ref = _make_db(
        existing={
            "status": "qualified",  # user edited
            "interactionCount": 3,
            "firstSeenAt": "<ts>",
            "createdAt": "<ts>",
        }
    )
    upsert_lead(
        db,
        "uid-1",
        sender_email="alice@acme.com",
        sender_name="Alice Chen",
        subject="Hello",
        subject_slug="hello",
        urgency="high",
        pdf_filename="y.pdf",
        suggested_response="urgent reply",
    )

    payload = ref.set.call_args.args[0]
    _check("subsequent write does NOT include 'status'", "status" not in payload)
    _check(
        "subsequent write does NOT include 'firstSeenAt'", "firstSeenAt" not in payload
    )
    _check("subsequent write does NOT include 'createdAt'", "createdAt" not in payload)
    _check("interactionCount increments to 4", payload.get("interactionCount") == 4)
    _check("urgency reflects latest email", payload.get("urgency") == "high")


def test_upsert_lead_never_raises() -> None:
    from firestore_leads import upsert_lead

    db = MagicMock()
    db.collection.side_effect = RuntimeError("simulated outage")
    raised: Exception | None = None
    try:
        upsert_lead(
            db,
            "uid",
            sender_email="x@y.com",
            sender_name="x",
            subject="s",
            subject_slug="s",
            urgency="low",
            pdf_filename="p",
            suggested_response="",
        )
    except Exception as exc:  # noqa: BLE001 - intentional
        raised = exc
    _check("upsert_lead is best-effort (does not raise)", raised is None)


def test_upsert_lead_skips_empty_inputs() -> None:
    from firestore_leads import upsert_lead

    db1 = MagicMock()
    upsert_lead(
        db1,
        "",
        sender_email="x@y.com",
        sender_name="x",
        subject="s",
        subject_slug="s",
        urgency="low",
        pdf_filename="p",
        suggested_response="",
    )
    _check("upsert_lead early-returns on empty uid", not db1.collection.called)

    db2 = MagicMock()
    upsert_lead(
        db2,
        "uid",
        sender_email="",
        sender_name="",
        subject="s",
        subject_slug="s",
        urgency="low",
        pdf_filename="p",
        suggested_response="",
    )
    _check("upsert_lead early-returns on empty sender_email", not db2.collection.called)


def test_parseaddr_handles_real_headers() -> None:
    cases = [
        ("Alice Chen <alice@acme.com>", ("Alice Chen", "alice@acme.com")),
        ("alice@acme.com", ("", "alice@acme.com")),
        ('"Lee, Bob" <bob@example.com>', ("Lee, Bob", "bob@example.com")),
        ("", ("", "")),
    ]
    bad = [(raw, parseaddr(raw), exp) for raw, exp in cases if parseaddr(raw) != exp]
    _check(
        "parseaddr handles all From: header shapes",
        not bad,
        "; ".join(f"{r!r}->{g!r} (expected {e!r})" for r, g, e in bad),
    )


# ---------------------------------------------------------------------------
# 2. Security
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (
        r'(?:api[_-]?key|secret|token|password)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']',
        "credential-shaped assignment",
    ),
    (r"AIza[0-9A-Za-z_\-]{35}", "Google API key literal"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI key literal"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key ID literal"),
]


def test_no_hardcoded_secrets() -> None:
    offenders: list[str] = []
    for f in PY_FILES:
        text = f.read_text(encoding="utf-8", errors="replace")
        for pat, desc in SECRET_PATTERNS:
            for m in re.finditer(pat, text):
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start : line_end if line_end != -1 else len(text)]
                if line.lstrip().startswith("#"):
                    continue
                ln = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{f.name}:{ln} {desc}")
    _check("no hardcoded secrets in *.py", not offenders, "; ".join(offenders))


def test_no_bare_except() -> None:
    offenders: list[str] = []
    pat = re.compile(r"^\s*except\s*:")
    for f in PY_FILES:
        for i, line in enumerate(
            f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if pat.match(line):
                offenders.append(f"{f.name}:{i}")
    _check("no bare 'except:' (Tier 1)", not offenders, ", ".join(offenders))


def test_no_eval_or_shell_injection() -> None:
    bad = [
        (r"\beval\s*\(", "eval()"),
        (r"\bexec\s*\(", "exec()"),
        (r"\bos\.system\s*\(", "os.system()"),
        (r"shell\s*=\s*True", "shell=True"),
    ]
    offenders: list[str] = []
    for f in PY_FILES:
        text = f.read_text(encoding="utf-8", errors="replace")
        for pat, desc in bad:
            for m in re.finditer(pat, text):
                ln = text.count("\n", 0, m.start()) + 1
                # skip comments and the test script itself describing the patterns
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start : line_end if line_end != -1 else len(text)]
                if line.lstrip().startswith("#"):
                    continue
                if f.name == "test_pipeline.py":
                    continue
                offenders.append(f"{f.name}:{ln} {desc}")
    _check("no eval/exec/os.system/shell=True", not offenders, "; ".join(offenders))


def test_gitignore_covers_sensitive_files() -> None:
    gi = REPO / ".gitignore"
    if not gi.exists():
        _check(".gitignore exists", False)
        return
    text = gi.read_text(encoding="utf-8", errors="replace")
    for needle in ("gmail_token.json", "gmail_credentials.json", ".env"):
        _check(f".gitignore covers {needle!r}", needle in text)


def test_firestore_rules_has_leads_allow() -> None:
    rules = REPO / "ui-platform/apps/email2ppt-portal/firestore.rules"
    if not rules.exists():
        _check("firestore.rules exists", False)
        return
    text = rules.read_text(encoding="utf-8", errors="replace")
    has_match = re.search(r"match\s+/leads/\{leadId\}", text) is not None
    _check("firestore.rules has match /leads/{leadId}", has_match)
    if has_match:
        # owner-or-admin allow inside the leads block
        block = re.search(
            r"match\s+/leads/\{leadId\}\s*\{(?P<body>[^}]*)\}", text, re.DOTALL
        )
        body = block.group("body") if block else ""
        _check(
            "firestore.rules /leads grants owner+admin",
            "isOwner(uid)" in body and "isAdmin()" in body,
        )


def test_secrets_loaded_from_env() -> None:
    """Tier 1: secrets must come from os.getenv at startup, not literals."""
    suspicious = []
    for f in PY_FILES:
        text = f.read_text(encoding="utf-8", errors="replace")
        # Look for any *_API_KEY or *_TOKEN assignment that's not from os.getenv
        for m in re.finditer(
            r"^([A-Z_]+(?:API_KEY|TOKEN|SECRET|PASSWORD))\s*=\s*(.+)$",
            text,
            re.MULTILINE,
        ):
            value = m.group(2).strip()
            if "os.getenv" in value or "os.environ" in value:
                continue
            if value.startswith(('"', "'")) and len(value) > 8:
                ln = text.count("\n", 0, m.start()) + 1
                suspicious.append(f"{f.name}:{ln} {m.group(1)}")
    _check(
        "secrets read from env (not string literals)",
        not suspicious,
        "; ".join(suspicious),
    )


# ---------------------------------------------------------------------------
# 3. Structure
# ---------------------------------------------------------------------------


def test_required_files_exist() -> None:
    required = [
        "firestore_leads.py",
        "firestore_folders.py",
        "watcher.py",
        "ui-platform/apps/email2ppt-portal/src/app/leads/page.tsx",
        "ui-platform/apps/email2ppt-portal/src/app/leads/loading.tsx",
        "ui-platform/apps/email2ppt-portal/src/app/leads/error.tsx",
        "ui-platform/apps/email2ppt-portal/src/lib/firebase.ts",
        "ui-platform/apps/email2ppt-portal/src/components/app-shell.tsx",
        "ui-platform/apps/email2ppt-portal/firestore.rules",
    ]
    for rel in required:
        _check(f"file exists: {rel}", (REPO / rel).exists())


def _all_calls_inside_try(source: str, name: str) -> tuple[bool, int]:
    """Return (every_call_in_try, total_calls)."""
    tree = ast.parse(source)
    calls_in_try: list[bool] = []
    try_stack: list[ast.Try] = []

    class V(ast.NodeVisitor):
        def visit_Try(self, node: ast.Try) -> None:
            try_stack.append(node)
            for stmt in node.body:
                self.visit(stmt)
            try_stack.pop()
            for h in node.handlers:
                self.visit(h)
            for stmt in node.finalbody:
                self.visit(stmt)
            for stmt in node.orelse:
                self.visit(stmt)

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            fname = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if fname == name:
                calls_in_try.append(bool(try_stack))
            self.generic_visit(node)

    V().visit(tree)
    return (all(calls_in_try) if calls_in_try else False, len(calls_in_try))


def test_watcher_integrates_lead_tracker() -> None:
    watcher_path = REPO / "watcher.py"
    if not watcher_path.exists():
        _check("watcher.py exists", False)
        return
    text = watcher_path.read_text(encoding="utf-8", errors="replace")
    _check(
        "watcher imports upsert_lead", "from firestore_leads import upsert_lead" in text
    )
    _check("watcher imports parseaddr", "from email.utils import parseaddr" in text)

    all_in_try, n = _all_calls_inside_try(text, "upsert_lead")
    _check(f"upsert_lead is called ({n} site{'s' if n != 1 else ''})", n >= 1)
    _check(
        "every upsert_lead call is inside a try-block (failure isolation)", all_in_try
    )


def test_portal_status_writes_use_merge() -> None:
    page = REPO / "ui-platform/apps/email2ppt-portal/src/app/leads/page.tsx"
    if not page.exists():
        _check("portal /leads page exists", False)
        return
    text = page.read_text(encoding="utf-8", errors="replace")
    _check("portal status update uses setDoc", "setDoc" in text)
    _check(
        "portal status update passes { merge: true }",
        re.search(r"merge:\s*true", text) is not None,
    )
    # Critical: the merge:true write must only include status + updatedAt,
    # NOT senderName/subject/etc — otherwise we'd clobber watcher-owned fields
    _check(
        "portal status payload only contains status + updatedAt",
        re.search(r"\{\s*status\s*,\s*updatedAt:\s*serverTimestamp\(\)\s*\}", text)
        is not None,
    )


def test_portal_path_helpers_exported() -> None:
    lib = REPO / "ui-platform/apps/email2ppt-portal/src/lib/firebase.ts"
    text = lib.read_text(encoding="utf-8", errors="replace")
    _check("userLeadsPath exported", "export const userLeadsPath" in text)
    _check("userLeadDocPath exported", "export const userLeadDocPath" in text)


def test_portal_nav_includes_leads() -> None:
    shell = REPO / "ui-platform/apps/email2ppt-portal/src/components/app-shell.tsx"
    text = shell.read_text(encoding="utf-8", errors="replace")
    _check("nav includes /leads link", '"/leads"' in text or "'/leads'" in text)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    _section("1. Pipeline (lead tracker semantics)")
    test_lead_id_determinism()
    test_upsert_lead_first_write()
    test_upsert_lead_preserves_user_status()
    test_upsert_lead_never_raises()
    test_upsert_lead_skips_empty_inputs()
    test_parseaddr_handles_real_headers()

    _section("2. Security")
    test_no_hardcoded_secrets()
    test_no_bare_except()
    test_no_eval_or_shell_injection()
    test_gitignore_covers_sensitive_files()
    test_firestore_rules_has_leads_allow()
    test_secrets_loaded_from_env()

    _section("3. Structure")
    test_required_files_exist()
    test_watcher_integrates_lead_tracker()
    test_portal_status_writes_use_merge()
    test_portal_path_helpers_exported()
    test_portal_nav_includes_leads()

    print(f"\n=== {_PASS} passed, {_FAIL} failed ===")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
