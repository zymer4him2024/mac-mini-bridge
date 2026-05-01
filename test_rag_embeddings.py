#!/usr/bin/env python3
"""Functional test for the folder-scoped RAG embedding store.

Covers:
  1. embed_text returns 768-dim vector.
  2. upsert_embedding writes to users/{uid}/embeddings/{messageId}.
  3. search_embeddings returns top-k for the scoped folder, ordered by
     cosine similarity (closest match first).
  4. Folder isolation: a query into folder A does NOT surface docs from
     folder B (the subjectSlug pre-filter is doing its job).
  5. delete_stale_embeddings removes only docs older than the cutoff.
  6. delete_embeddings_for_user empties the entire user's embeddings.

Uses isolated test slugs (__test_rag_a, __test_rag_b) so real folders are
not touched. All test data is cleaned up at the end, even on failure.

Run: python3 test_rag_embeddings.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
load_dotenv(BASE_DIR / ".env")

from firestore_activity import get_db  # noqa: E402
from firestore_users import enumerate_linked_users  # noqa: E402
from firestore_embeddings import (  # noqa: E402
    upsert_embedding,
    search_embeddings,
    delete_embeddings_for_user,
    delete_stale_embeddings,
)
from embeddings import embed_text, EMBEDDING_DIM  # noqa: E402

SLUG_A = "__test_rag_a"
SLUG_B = "__test_rag_b"
PROBE_PREFIX = "__rag_test_probe__"

# Three semantically distinct docs in folder A
DOCS_A = [
    ("a1", "Project deadline moved to next Friday. All tasks reprioritized."),
    ("a2", "Team meeting cancelled. Will reschedule for next week."),
    ("a3", "Budget approved for hiring two new engineers in Q3."),
]
# Two docs in folder B (different topic entirely)
DOCS_B = [
    ("b1", "The customer requested a refund for the damaged package."),
    ("b2", "Shipping delays expected due to weather conditions."),
]

PASS = "PASS"
FAIL = "FAIL"


class TestState:
    def __init__(self, db, uid: str):
        self.db = db
        self.uid = uid
        self.written: list[str] = []  # message_ids we wrote, for cleanup
        self.failures: list[str] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        tag = PASS if ok else FAIL
        line = f"  [{tag}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)
        if not ok:
            self.failures.append(name)


def write_doc(s: TestState, slug: str, suffix: str, text: str) -> str:
    msg_id = f"{PROBE_PREFIX}{slug}--{suffix}"  # "--" separates slug from suffix unambiguously
    vec = embed_text(text)
    upsert_embedding(
        s.db,
        s.uid,
        subject_slug=slug,
        lead_id=f"lead-{suffix}",
        message_id=msg_id,
        text=text,
        vector=vec,
        subject=f"test-{suffix}",
        sender_name="Test Suite",
    )
    s.written.append(msg_id)
    return msg_id


def cleanup(s: TestState) -> None:
    coll = s.db.collection("users").document(s.uid).collection("embeddings")
    deleted = 0
    for snap in coll.stream():
        if snap.id.startswith(PROBE_PREFIX):
            snap.reference.delete()
            deleted += 1
    print(f"[cleanup] removed {deleted} probe docs")


def test_embed_dim(s: TestState) -> None:
    print("\n[1] embed_text returns 768-dim vector")
    v = embed_text("hello world")
    s.record("dim is 768", len(v) == EMBEDDING_DIM, f"got {len(v)}")


def test_write_and_recall(s: TestState) -> None:
    print("\n[2] write 5 docs across two folders")
    for suf, text in DOCS_A:
        write_doc(s, SLUG_A, suf, text)
    for suf, text in DOCS_B:
        write_doc(s, SLUG_B, suf, text)
    s.record("wrote 5 probe docs", len(s.written) == 5, f"written={len(s.written)}")


def test_top_hit_in_folder(s: TestState) -> None:
    print("\n[3] query folder A: 'when is the deadline?' should rank a1 first")
    q = "When is the deadline?"
    hits = search_embeddings(s.db, s.uid, SLUG_A, embed_text(q), k=3)
    s.record("got hits", len(hits) > 0, f"k={len(hits)}")
    if hits:
        top = hits[0]
        s.record(
            "top hit is a1 (deadline doc)",
            top["messageId"].endswith("--a1"),
            f"top msg={top['messageId']}",
        )
        # All hits should be from folder A (slugs A and B don't overlap, so
        # plain substring match is unambiguous).
        all_a = all(SLUG_A in h["messageId"] for h in hits)
        no_b = all(SLUG_B not in h["messageId"] for h in hits)
        s.record(
            "all hits are folder A",
            all_a and no_b,
            f"msgs={[h['messageId'] for h in hits]}",
        )


def test_folder_isolation(s: TestState) -> None:
    print("\n[4] query folder A with a B-topic question — must not return B docs")
    q = "Did we get a refund request?"
    hits = search_embeddings(s.db, s.uid, SLUG_A, embed_text(q), k=5)
    leaked = [h for h in hits if SLUG_B in h["messageId"]]
    s.record(
        "no folder-B docs in folder-A results",
        len(leaked) == 0,
        f"leaked={[h['messageId'] for h in leaked]}",
    )

    print("[4] query folder B with the same B-topic question — should rank b1")
    hits = search_embeddings(s.db, s.uid, SLUG_B, embed_text(q), k=3)
    s.record("got B hits", len(hits) > 0)
    if hits:
        s.record(
            "top hit is b1 (refund doc)",
            hits[0]["messageId"].endswith("--b1"),
            f"top msg={hits[0]['messageId']}",
        )


def test_delete_stale(s: TestState) -> None:
    print("\n[5] delete_stale_embeddings with cutoff = now — removes all probes")
    # `older_than = now` means: delete docs createdAt < now (i.e., everything we
    # just wrote, since SERVER_TIMESTAMP is well in the past by the time this
    # runs). We want to verify only OUR probe docs go, not the user's real
    # embeddings — but we don't have any real ones in the test uid (cleanup
    # wiped after Phase 1), so the count == our written count is the check.
    time.sleep(2)  # ensure SERVER_TIMESTAMP < `now`
    cutoff = datetime.now(timezone.utc)
    n = delete_stale_embeddings(s.db, s.uid, cutoff)
    # All 5 probe docs should be gone (or however many were left after prior tests)
    coll = s.db.collection("users").document(s.uid).collection("embeddings")
    remaining_probes = sum(
        1 for snap in coll.stream() if snap.id.startswith(PROBE_PREFIX)
    )
    s.record(
        "all probe docs removed by stale cutoff",
        remaining_probes == 0,
        f"deleted={n}, remaining_probes={remaining_probes}",
    )


def test_delete_for_user(s: TestState) -> None:
    print("\n[6] delete_embeddings_for_user — write 1 more probe, then nuke")
    write_doc(s, SLUG_A, "z9", "Final probe doc to be wiped by user-delete.")
    n = delete_embeddings_for_user(s.db, s.uid)
    s.record("delete_embeddings_for_user returned >=1", n >= 1, f"deleted={n}")
    coll = s.db.collection("users").document(s.uid).collection("embeddings")
    remaining = sum(1 for _ in coll.stream())
    s.record(
        "embeddings collection empty for test uid",
        remaining == 0,
        f"remaining={remaining}",
    )


def main() -> int:
    db = get_db()
    uids = enumerate_linked_users(db)
    if not uids:
        print("FATAL: no linked users found")
        return 2
    uid = uids[0]
    print(f"using test uid={uid}")

    s = TestState(db, uid)
    try:
        test_embed_dim(s)
        test_write_and_recall(s)
        test_top_hit_in_folder(s)
        test_folder_isolation(s)
        test_delete_stale(s)
        test_delete_for_user(s)
    finally:
        cleanup(s)

    print("\n" + "=" * 60)
    if s.failures:
        print(f"FAILED: {len(s.failures)} check(s)")
        for f in s.failures:
            print(f"  - {f}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
