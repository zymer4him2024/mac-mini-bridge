#!/usr/bin/env python3
"""Single-query CLI smoke test for the live RAG read pipeline.

Calls `rag_core.answer_question` against production Firestore + Ollama for one
(uid, slug, subject, question) tuple, then prints retrieval diagnostics + the
final answer. Reuses the production code path verbatim so a clean run means
the same path the bridge uses is wired correctly.

Read-only. Writes nothing to Firestore. Run on the host where bridge.py runs
(Mac mini), under the same venv:

    ./venv/bin/python tests/smoke_rag.py \\
        --uid lRyuYHeqE4bdATrO50cMEr8p79a2 \\
        --slug test-요즘-한국에서-가장-유명한-음식 \\
        --subject "Fwd: Test: 요즘 한국에서 가장 유명한 음식" \\
        --question "음식 추천해줘"

Exit code is always 0 — this is a diagnostic, not a pass/fail gate. Use
tests/eval/rag_eval.py for that.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR))

from embeddings import embed_text  # noqa: E402
from firestore_activity import get_db  # noqa: E402
from firestore_embeddings import search_embeddings  # noqa: E402
from rag_core import RAG_K, answer_question  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--uid", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--k", type=int, default=RAG_K)
    args = p.parse_args()

    db = get_db()

    print("=== smoke_rag ===")
    print(f"uid:      {args.uid}")
    print(f"slug:     {args.slug}")
    print(f"subject:  {args.subject}")
    print(f"question: {args.question}")
    print(f"k:        {args.k}")
    print()

    qvec = embed_text(args.question)
    hits = search_embeddings(db, args.uid, args.slug, qvec, k=args.k)

    print(f"retrieved {len(hits)} hit(s):")
    for i, h in enumerate(hits, 1):
        sender = h.get("senderName") or "(unknown)"
        subj = (h.get("subject") or "")[:60]
        print(f"  [{i}] dist={h.get('distance', 1.0):.3f} from={sender} subj={subj}")
    print()

    answer, meta = answer_question(
        db,
        args.uid,
        args.slug,
        args.subject,
        args.question,
        k=args.k,
    )
    print(f"meta: {meta}")
    print()
    print("answer:")
    print(answer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
