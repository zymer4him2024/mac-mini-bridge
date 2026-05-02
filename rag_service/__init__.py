"""Web-facing HTTP wrapper around rag_core.

Authenticates the caller via Firebase ID token, validates the request with
Pydantic, then delegates to `rag_core.answer_question`. Lives alongside the
Python pipeline so it can import rag_core / firestore helpers / embeddings
directly. The web client at apps/shomery-web/ is its only intended caller.
"""
