"""Firebase ID token verification dependency for FastAPI routes.

The web client gets a Firebase ID token via firebase-auth in the browser and
sends it as `Authorization: Bearer <token>`. This dependency verifies the
token via firebase-admin and returns the uid; routes use it to scope all
work to the authenticated user.

Tests inject a fake verify function via app.dependency_overrides[get_uid].
"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, status
from firebase_admin import auth as fb_auth

log = logging.getLogger("rag_service.auth")


def get_uid(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: parse and verify Bearer token, return uid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token",
        )
    try:
        decoded = fb_auth.verify_id_token(token)
    except (fb_auth.InvalidIdTokenError, ValueError) as exc:
        log.info("verify_id_token rejected: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    uid = decoded.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has no uid",
        )
    return uid
