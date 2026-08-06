"""Helpers for minting HS256 JWTs in tests (dependency-free).

Mirrors the encoding the :class:`HS256TokenVerifier` verifies, so tests can mint
valid (and deliberately invalid) tokens offline without any JWT library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

#: The default HS256 secret from Settings (tests use the default settings).
DEFAULT_SECRET = "dev-insecure-hs256-secret-change-me"
ISSUER = "complianceiq-core"
AUDIENCE = "complianceiq"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def mint_token(
    *,
    secret: str = DEFAULT_SECRET,
    sub: str = "user-1",
    tenant_id: str = "tenant-a",
    roles: list[str] | None = None,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_in: int = 3600,
    algorithm: str = "HS256",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Mint an HS256 JWT with the given claims (all overridable for negative tests)."""
    header = {"alg": algorithm, "typ": "JWT"}
    claims: dict[str, Any] = {
        "sub": sub,
        "tenant_id": tenant_id,
        "roles": roles if roles is not None else ["analyst"],
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + expires_in,
    }
    if extra_claims:
        claims.update(extra_claims)
    header_b64 = _b64(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64(json.dumps(claims).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = _b64(hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header_b64}.{payload_b64}.{signature}"


def bearer(token: str) -> dict[str, str]:
    """Wrap a token in an Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}
