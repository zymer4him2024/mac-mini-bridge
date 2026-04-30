#!/usr/bin/env python3
"""Folder-scoped RAG eval runner.

Reads YAML test cases, runs the live pipeline (embed → search → ground),
and reports per-stage metrics:
  - Retrieval: top-k hits cleared the threshold? expected lead_ids present?
  - Generation: required keywords present? forbidden keywords absent?
                refusal correctly emitted on out-of-scope queries?

Calls the lower-level RAG primitives directly (embed_text, search_embeddings,
grounded_answer) rather than rag_core.answer_question, because we need the
intermediate hits list to compute recall.

Reads from production Firestore + Ollama. Writes nothing back. Run on the
host where bridge.py runs (Mac mini), under the same venv:

    ./venv/bin/python tests/eval/rag_eval.py --cases tests/eval/cases.yaml

Exit code 0 if all cases pass, 1 if any fail.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR))

import embeddings  # noqa: E402
import rag_core  # noqa: E402
from embeddings import embed_text  # noqa: E402
from firestore_activity import get_db  # noqa: E402
from firestore_embeddings import search_embeddings  # noqa: E402
from rag_core import (  # noqa: E402
    RAG_DISTANCE_THRESHOLD,
    RAG_K,
    grounded_answer,
)


def _provenance() -> dict[str, Any]:
    """Snapshot of which models / endpoints this eval run used. Recorded in
    the JSON dump so future score deltas can be attributed to model swaps
    vs code regressions."""
    return {
        "embedding_model": embeddings.EMBEDDING_MODEL,
        "embedding_version": embeddings.EMBEDDING_VERSION,
        "embedding_dim": embeddings.EMBEDDING_DIM,
        "embedding_base_url": embeddings.OLLAMA_BASE_URL,
        "llm_model": rag_core.OLLAMA_MODEL,
        "llm_base_url": rag_core.OLLAMA_BASE_URL,
    }

REFUSAL_MARKER = "I don't have"

log = logging.getLogger("rag_eval")


@dataclass
class CaseResult:
    name: str
    hits: list[dict[str, Any]] = field(default_factory=list)
    relevant_count: int = 0
    top_distance: float = 1.0
    answer: str = ""
    retrieval_pass: bool = False
    retrieval_failures: list[str] = field(default_factory=list)
    generation_pass: bool = False
    generation_failures: list[str] = field(default_factory=list)

    @property
    def overall_pass(self) -> bool:
        return self.retrieval_pass and self.generation_pass


def _load_cases(path: Path) -> list[dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a top-level list of cases")
    seen_names: set[str] = set()
    for i, case in enumerate(raw):
        if not isinstance(case, dict):
            raise ValueError(f"{path}: case #{i} is not a mapping")
        for required in ("name", "uid", "subject_slug", "subject", "question"):
            if not case.get(required):
                raise ValueError(f"{path}: case #{i} missing {required!r}")
        if case["name"] in seen_names:
            raise ValueError(f"{path}: duplicate case name {case['name']!r}")
        seen_names.add(case["name"])
    return raw


def _score_retrieval(case: dict, hits: list[dict], threshold: float) -> tuple[bool, list[str]]:
    failures: list[str] = []
    relevant = [h for h in hits if h.get("distance", 1.0) <= threshold]
    top_dist = hits[0]["distance"] if hits else 1.0

    expected_ids = case.get("expected_lead_ids")
    if expected_ids:
        retrieved_ids = {h.get("leadId", "") for h in hits}
        if not retrieved_ids.intersection(expected_ids):
            failures.append(
                f"expected_lead_ids: none of {expected_ids} in top-{len(hits)} "
                f"({sorted(retrieved_ids)})"
            )

    max_top = case.get("max_top_distance")
    if max_top is not None and top_dist > float(max_top):
        failures.append(f"top_distance {top_dist:.3f} > {max_top}")

    min_rel = case.get("min_relevant_count")
    if min_rel is not None and len(relevant) < int(min_rel):
        failures.append(f"relevant {len(relevant)} < {min_rel}")

    return (not failures), failures


def _score_generation(case: dict, answer: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    answer_lc = answer.lower()

    if case.get("expected_refusal"):
        if REFUSAL_MARKER.lower() not in answer_lc:
            failures.append(f"expected refusal (containing {REFUSAL_MARKER!r}) but got: {answer[:80]!r}")
        return (not failures), failures

    for kw in (case.get("expected_keywords") or []):
        if kw.lower() not in answer_lc:
            failures.append(f"missing keyword: {kw!r}")

    for kw in (case.get("forbidden_keywords") or []):
        if kw.lower() in answer_lc:
            failures.append(f"forbidden keyword present: {kw!r}")

    return (not failures), failures


def _run_case(
    db, case: dict, *, threshold: float, k: int, run_generation: bool, uid_override: str | None,
) -> CaseResult:
    res = CaseResult(name=case["name"])
    uid = uid_override or case["uid"]
    slug = case["subject_slug"]
    subject = case["subject"]
    question = case["question"]

    try:
        qvec = embed_text(question)
        hits = search_embeddings(db, uid, slug, qvec, k=k)
    except Exception as exc:  # noqa: BLE001 — eval surfaces all failures
        res.retrieval_failures.append(f"retrieval raised: {exc!r}")
        return res

    res.hits = hits
    res.top_distance = hits[0]["distance"] if hits else 1.0
    res.relevant_count = sum(1 for h in hits if h.get("distance", 1.0) <= threshold)
    res.retrieval_pass, res.retrieval_failures = _score_retrieval(case, hits, threshold)

    if not run_generation:
        # Skip generation scoring entirely; report retrieval only.
        res.generation_pass = True
        return res

    relevant = [h for h in hits if h.get("distance", 1.0) <= threshold]
    if case.get("expected_refusal") or not relevant:
        res.answer = (
            f"I don't have anything in folder '{subject[:60]}' about that. "
            f"Try /folders to switch."
        )
    else:
        try:
            res.answer = grounded_answer(question, subject, relevant)
        except Exception as exc:  # noqa: BLE001
            res.generation_failures.append(f"generation raised: {exc!r}")
            return res

    res.generation_pass, res.generation_failures = _score_generation(case, res.answer)
    return res


def _format_row(idx: int, total: int, res: CaseResult, case: dict) -> str:
    status = "PASS" if res.overall_pass else "FAIL"
    retr = "ok" if res.retrieval_pass else f"FAIL({'; '.join(res.retrieval_failures)})"
    if case.get("expected_refusal"):
        gen = "refusal-ok" if res.generation_pass else f"FAIL({'; '.join(res.generation_failures)})"
    else:
        n_keywords = len(case.get("expected_keywords") or []) + len(case.get("forbidden_keywords") or [])
        n_failures = len(res.generation_failures)
        gen = (
            f"{n_keywords - n_failures}/{n_keywords}" if n_keywords
            else ("ok" if res.generation_pass else "FAIL")
        )
        if n_failures:
            gen += f" ({'; '.join(res.generation_failures)})"
    return (
        f"[{idx}/{total}] {status} {res.name:<40} "
        f"retr={retr} faith={gen} dist={res.top_distance:.3f}"
    )


def _print_summary(results: list[CaseResult], cases: list[dict]) -> None:
    total = len(results)
    if not total:
        print("no cases run")
        return
    retr_pass = sum(1 for r in results if r.retrieval_pass)
    gen_pass = sum(1 for r in results if r.generation_pass)
    leak = sum(
        1 for r, c in zip(results, cases)
        if any("forbidden" in f for f in r.generation_failures) and (c.get("forbidden_keywords") or [])
    )
    refusal_cases = [c for c in cases if c.get("expected_refusal")]
    refusal_correct = sum(
        1 for r, c in zip(results, cases)
        if c.get("expected_refusal") and r.generation_pass
    )
    mean_top = sum(r.top_distance for r in results) / total

    print()
    print(f"retrieval_recall@{RAG_K:<2}    {retr_pass}/{total}  ({retr_pass / total:.2f})")
    print(f"faithfulness          {gen_pass}/{total}  ({gen_pass / total:.2f})")
    print(f"leak_rate             {leak}/{total}  ({leak / total:.2f})")
    if refusal_cases:
        print(
            f"refusal_correctness   {refusal_correct}/{len(refusal_cases)}  "
            f"({refusal_correct / len(refusal_cases):.2f})"
        )
    print(f"mean_top_distance     {mean_top:.3f}")


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--cases", type=Path, default=Path(__file__).parent / "cases.yaml")
    p.add_argument("--out", type=Path, default=None, help="JSON dump path for per-case results")
    p.add_argument("--uid", default=None, help="override per-case uid (handy for dry-runs)")
    p.add_argument("--threshold", type=float, default=RAG_DISTANCE_THRESHOLD)
    p.add_argument("--k", type=int, default=RAG_K)
    p.add_argument("--no-generation", action="store_true", help="retrieval-only; skip Ollama LLM calls")
    args = p.parse_args()

    cases = _load_cases(args.cases)
    if not cases:
        print(f"no cases in {args.cases}", file=sys.stderr)
        return 1

    prov = _provenance()
    print("=== rag_eval ===")
    print(f"embedding: {prov['embedding_model']} (v={prov['embedding_version']}) @ {prov['embedding_base_url']}")
    print(f"llm:       {prov['llm_model']} @ {prov['llm_base_url']}")
    print(f"threshold: {args.threshold}  k: {args.k}  generation: {'skipped' if args.no_generation else 'enabled'}")
    print()

    db = get_db()
    results: list[CaseResult] = []
    for i, case in enumerate(cases, 1):
        res = _run_case(
            db, case,
            threshold=args.threshold, k=args.k,
            run_generation=not args.no_generation,
            uid_override=args.uid,
        )
        results.append(res)
        print(_format_row(i, len(cases), res, case))

    _print_summary(results, cases)

    if args.out:
        payload = {
            "threshold": args.threshold,
            "k": args.k,
            "generation_skipped": args.no_generation,
            "provenance": prov,
            "results": [
                {**asdict(r), "case": {k_: v for k_, v in c.items()}}
                for r, c in zip(results, cases)
            ],
        }
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.out}")

    return 0 if all(r.overall_pass for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
