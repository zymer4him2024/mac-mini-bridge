"""HTTP-level tests for rag_service.main.

Uses FastAPI's TestClient with dependency overrides for Firestore, LLM, and
auth — so the tests don't touch the real Ollama, Firebase, or Firestore.
The boundary we exercise is: request shape, auth, and the call into
rag_core.answer_question (which is patched).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from rag_service.auth import get_uid
from rag_service.main import app, db_dep, llm_dep


_VALID_BODY = {
    "question": "What did Acme say about budget?",
    "subject_slug": "acme-pilot",
    "subject_display": "Acme pilot",
}


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[db_dep] = lambda: object()  # opaque marker
    app.dependency_overrides[llm_dep] = lambda: (object(), "test-model")
    app.dependency_overrides[get_uid] = lambda: "test-uid"
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_healthz_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model"] == "test-model"


def test_ask_happy_path_returns_reply_and_meta(client: TestClient) -> None:
    fake_meta = {"error": None, "hits": 5, "relevant": 3, "top_dist": 0.42}
    with patch(
        "rag_service.main.answer_question",
        return_value=("Acme is targeting a $40k pilot.", fake_meta),
    ) as mocked:
        response = client.post("/ask", json=_VALID_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Acme is targeting a $40k pilot."
    assert body["meta"] == fake_meta

    # answer_question received the validated request fields and the test uid.
    args, kwargs = mocked.call_args
    _db, uid, slug, subject, question = args
    assert uid == "test-uid"
    assert slug == "acme-pilot"
    assert subject == "Acme pilot"
    assert question == "What did Acme say about budget?"
    # Web overrides the Telegram-flavored refusal suffix.
    assert kwargs.get("refusal_suffix") == ""
    # The injected LLM model from the dependency override is forwarded.
    assert kwargs.get("llm_model") == "test-model"


def test_ask_passes_refusal_through(client: TestClient) -> None:
    """A refusal from rag_core comes back to the client as-is."""
    refusal = "I don't have anything in folder 'Acme pilot' about that."
    refusal_meta = {"error": None, "hits": 5, "relevant": 0, "top_dist": 0.83}
    with patch(
        "rag_service.main.answer_question",
        return_value=(refusal, refusal_meta),
    ):
        response = client.post("/ask", json=_VALID_BODY)

    assert response.status_code == 200
    assert response.json()["reply"] == refusal


def test_ask_passes_error_reply_through(client: TestClient) -> None:
    """Infrastructure failure in rag_core surfaces as a normal 200 reply."""
    error_reply = "Something went wrong on our end. We've logged it."
    error_meta = {"error": "retrieval", "hits": 0, "relevant": 0, "top_dist": 1.0}
    with patch(
        "rag_service.main.answer_question",
        return_value=(error_reply, error_meta),
    ):
        response = client.post("/ask", json=_VALID_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == error_reply
    assert body["meta"]["error"] == "retrieval"


def test_ask_rejects_missing_authorization() -> None:
    """Without the get_uid override, the real dependency runs and rejects."""
    # Override only db + llm, leave get_uid live so it enforces the header.
    app.dependency_overrides[db_dep] = lambda: object()
    app.dependency_overrides[llm_dep] = lambda: (object(), "test-model")
    try:
        client = TestClient(app)
        response = client.post("/ask", json=_VALID_BODY)
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing bearer token"
    finally:
        app.dependency_overrides.clear()


def test_ask_rejects_empty_question(client: TestClient) -> None:
    bad_body = {**_VALID_BODY, "question": ""}
    response = client.post("/ask", json=bad_body)
    assert response.status_code == 422


def test_ask_rejects_missing_subject_slug(client: TestClient) -> None:
    bad_body = {k: v for k, v in _VALID_BODY.items() if k != "subject_slug"}
    response = client.post("/ask", json=bad_body)
    assert response.status_code == 422


def test_ask_rejects_oversized_question(client: TestClient) -> None:
    bad_body = {**_VALID_BODY, "question": "x" * 2001}
    response = client.post("/ask", json=bad_body)
    assert response.status_code == 422
