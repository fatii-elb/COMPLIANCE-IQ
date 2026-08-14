"""HS256 development-token minter (dependency-free).

The Core Service issues real JWTs in production; this service only *verifies*
them. For local development and client testing we still need a way to obtain a
valid token, so this module mints short-lived HS256 tokens with the same shared
secret the HS256 verifier checks — using nothing but the standard library, the
mirror image of :class:`HS256TokenVerifier`.

This is a **development affordance only**. It is exposed over HTTP solely by the
LOCAL-gated ``/api/v1/auth/dev-token`` endpoint and by the ``mint_dev_token``
script — never in production, and it grants no capability that a genuine
Core-issued token would not.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Sequence

from complianceiq.infrastructure.auth.jwt_base import b64url_encode


def mint_hs256_token(
    *,
    secret: str,
    issuer: str,
    audience: str,
    subject: str,
    tenant_id: str,
    roles: Sequence[str] = (),
    ttl_seconds: int = 3600,
    now: int | None = None,
) -> tuple[str, int]:
    """Mint an HS256 JWT accepted by the HS256 verifier.

    Args:
        secret: The shared HS256 secret (``CIQ_JWT_HS256_SECRET``).
        issuer: The ``iss`` claim (must match ``jwt_issuer``).
        audience: The ``aud`` claim (must match ``jwt_audience``).
        subject: The ``sub`` claim (the principal).
        tenant_id: The ``tenant_id`` claim — scopes every downstream call.
        roles: The ``roles`` claim (RBAC).
        ttl_seconds: Lifetime of the token from now.
        now: Override the current epoch seconds (for tests); defaults to wall time.

    Returns:
        A ``(token, expires_at_epoch)`` tuple.
    """
    issued_at = int(time.time()) if now is None else now
    expires_at = issued_at + ttl_seconds
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": list(roles),
        "iss": issuer,
        "aud": audience,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
    }
    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    signature_b64 = b64url_encode(signature)
    return f"{signing_input}.{signature_b64}", expires_at
