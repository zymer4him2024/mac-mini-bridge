"""KMS envelope wrap/unwrap for refresh tokens and bot tokens.

Soak-window contract:

  - Stored values prefixed with `kms:v1:` are KMS ciphertexts (base64 of
    the raw KMS Encrypt output, prepended with the marker).
  - Anything without the prefix is plaintext from a pre-KMS write. Reader
    returns it untouched so existing tokens keep working until the
    migration sweep upgrades them.
  - When `KMS_KEY_NAME` is unset, encryption is a no-op. This lets us
    deploy the read path before the infra is provisioned. A startup log
    line surfaces the missing config so operators notice.

Activation: set `KMS_KEY_NAME` in the worker's `.env`:

  KMS_KEY_NAME=projects/<proj>/locations/<loc>/keyRings/<kr>/cryptoKeys/<k>
"""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache

log = logging.getLogger("kms_envelope")

CIPHERTEXT_PREFIX = "kms:v1:"
ENV_KEY = "KMS_KEY_NAME"


@lru_cache(maxsize=1)
def _client():
    from google.cloud import kms

    return kms.KeyManagementServiceClient()


def kms_configured() -> bool:
    return bool(os.environ.get(ENV_KEY, "").strip())


def wrap_token(plaintext: str) -> str:
    """Return base64 ciphertext (with marker) or plaintext if KMS not set."""
    if not plaintext:
        return plaintext
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        return plaintext
    resp = _client().encrypt(
        request={"name": key, "plaintext": plaintext.encode("utf-8")}
    )
    return CIPHERTEXT_PREFIX + base64.b64encode(resp.ciphertext).decode("ascii")


def unwrap_token(value: str) -> str:
    """Return plaintext. Pass-through for non-prefixed values."""
    if not value or not value.startswith(CIPHERTEXT_PREFIX):
        return value
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        log.error(
            "encountered ciphertext but %s is unset; cannot unwrap", ENV_KEY
        )
        raise RuntimeError("kms_not_configured")
    ciphertext = base64.b64decode(value[len(CIPHERTEXT_PREFIX):])
    resp = _client().decrypt(request={"name": key, "ciphertext": ciphertext})
    return resp.plaintext.decode("utf-8")
