"""Per-message embedding store for folder-scoped RAG.

Layout: users/{uid}/embeddings/{messageId}
Fields: leadId, subjectSlug, embeddingVersion, text, vector, subject,
        senderName, createdAt

The Firestore SDK calls in this file are the only place outside `firestore_*`
modules that read/write the embeddings collection. All other code (watcher,
bridge, backfill) goes through these helpers.

Vector index requirement (one-time, per project + named DB):
  gcloud firestore indexes composite create \\
    --project=simpleios01 --database=email2ppt \\
    --collection-group=embeddings --query-scope=COLLECTION \\
    --field-config=vector-config='{"dimension":"768","flat":"{}"}',field-path=vector
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from google.api_core import exceptions as gax
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from embeddings import EMBEDDING_DIM, EMBEDDING_VERSION

log = logging.getLogger("firestore_embeddings")


def upsert_embedding(
    db,
    uid: str,
    *,
    subject_slug: str,
    lead_id: str,
    message_id: str,
    text: str,
    vector: list[float],
    subject: str = "",
    sender_name: str = "",
) -> None:
    """Write one embedding doc. Caller is responsible for try/except in
    best-effort paths (watcher hook). Raises on validation errors."""
    if not uid or not message_id:
        raise ValueError("upsert_embedding: uid and message_id required")
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(
            f"upsert_embedding: vector dim {len(vector)} != {EMBEDDING_DIM}"
        )

    ref = (
        db.collection("users")
        .document(uid)
        .collection("embeddings")
        .document(message_id)
    )
    ref.set(
        {
            "leadId": lead_id,
            "subjectSlug": subject_slug,
            "embeddingVersion": EMBEDDING_VERSION,
            "text": text,
            "vector": Vector(vector),
            "subject": subject or "",
            "senderName": sender_name or "",
            "createdAt": SERVER_TIMESTAMP,
        },
        merge=True,
    )


def search_embeddings(
    db,
    uid: str,
    subject_slug: str,
    query_vector: list[float],
    k: int = 5,
) -> list[dict[str, Any]]:
    """Return top-k embedding docs in (uid, subject_slug), sorted by cosine
    distance ascending (closest match first).

    Each result: {messageId, leadId, text, subject, senderName, distance}.
    `distance` is cosine distance (0 = identical, 1 = orthogonal); callers
    apply a threshold for NotebookLM-style "no relevant context" refusals.

    Pre-filters by subject_slug so the vector index only scans that folder.
    """
    if len(query_vector) != EMBEDDING_DIM:
        raise ValueError(
            f"search_embeddings: vector dim {len(query_vector)} != {EMBEDDING_DIM}"
        )
    coll = (
        db.collection("users").document(uid).collection("embeddings")
    )
    q = coll.where("subjectSlug", "==", subject_slug).find_nearest(
        vector_field="vector",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=k,
        distance_result_field="_distance",
    )
    out: list[dict[str, Any]] = []
    for snap in q.get():
        d = snap.to_dict() or {}
        out.append(
            {
                "messageId": snap.id,
                "leadId": d.get("leadId", ""),
                "text": d.get("text", ""),
                "subject": d.get("subject", ""),
                "senderName": d.get("senderName", ""),
                "distance": float(d.get("_distance", 0.0)),
            }
        )
    return out


def delete_embeddings_for_user(db, uid: str) -> int:
    """GDPR helper. Deletes every doc under users/{uid}/embeddings.
    Returns the number of docs deleted."""
    coll = db.collection("users").document(uid).collection("embeddings")
    deleted = 0
    for snap in coll.stream():
        try:
            snap.reference.delete()
            deleted += 1
        except gax.GoogleAPIError as exc:
            log.warning(
                "delete_embeddings_for_user: failed on %s: %s", snap.id, exc
            )
    return deleted


def delete_stale_embeddings(db, uid: str, older_than: datetime) -> int:
    """Retention helper. Deletes docs where createdAt < older_than."""
    coll = db.collection("users").document(uid).collection("embeddings")
    q = coll.where("createdAt", "<", older_than)
    deleted = 0
    for snap in q.stream():
        try:
            snap.reference.delete()
            deleted += 1
        except gax.GoogleAPIError as exc:
            log.warning(
                "delete_stale_embeddings: failed on %s: %s", snap.id, exc
            )
    return deleted
