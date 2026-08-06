"""A dependency-free HS256 JWT verifier (Phase 5).

This adapter implements the :class:`TokenVerifier` port using **HMAC-SHA256**
(HS256), a symmetric JWT scheme, with nothing but the Python standard library —
no crypto packages, no cffi. It verifies the signature and the standard claims
(``exp``, ``nbf``, ``iss``, ``aud``) before trusting anything, then projects
``sub``/``tenant_id``/``roles`` into an :class:`AuthContext`.

Why HS256 here, RS256 later? HS256 is a legitimate, secure choice for local
development and offline testing (a shared secret both mints and verifies). The
Core Service will sign real tokens **asymmetrically** (RS256/ES256) and hand us
only its *public* key; that verifier is Phase 6 and implements the very same
port, so no caller changes.

Security notes baked in below:
- The algorithm is pinned to ``HS256``. A token whose header says ``none`` or
  ``RS256`` is rejected outright — this closes the classic *algorithm-confusion*
  attack where an attacker downgrades to ``none`` or tricks an RS256 verifier
  into treating the public key as an HMAC secret.
- Signature comparison uses :func:`hmac.compare_digest` (constant time), so a
  timing side-channel can't be used to forge a signature byte by byte.
- Errors never echo the token, the secret, or the computed signature.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from typing import Any

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import AuthenticationError, ValidationError
from complianceiq.domain.ports.auth import TokenVerifier
from complianceiq.domain.ports.clock import Clock

_ALGORITHM = "HS256"


def _b64url_decode(segment: str) -> bytes:
    """Decode a base64url segment, tolerating missing padding."""
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (binascii.Error, ValueError) as exc:
        raise AuthenticationError("malformed token encoding") from exc


def _b64url_encode(raw: bytes) -> str:
    """Encode bytes as an unpadded base64url string (used for signing)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class HS256TokenVerifier(TokenVerifier):
    """Verify HS256-signed JWTs against a shared secret (Phase 5)."""

    def __init__(
        self,
        *,
        secret: str,
        issuer: str,
        audience: str,
        clock: Clock,
        leeway_seconds: int = 60,
    ) -> None:
        if not secret:
            # Fail loudly at construction rather than accept-everything at runtime.
            raise ValidationError("HS256 token verifier requires a non-empty secret")
        self._secret = secret.encode("utf-8")
        self._issuer = issuer
        self._audience = audience
        self._clock = clock
        self._leeway = leeway_seconds

    def verify(self, token: str) -> AuthContext:
        """Verify ``token`` and project its claims into an ``AuthContext``."""
        header_b64, payload_b64 = self._split(token)
        self._check_algorithm(header_b64)
        signing_input = f"{header_b64}.{payload_b64}"
        self._check_signature(signing_input, token)
        claims = self._decode_claims(payload_b64)
        self._check_temporal(claims)
        self._check_issuer_audience(claims)
        return self._to_auth_context(claims)

    # ------------------------------------------------------------------ steps

    def _split(self, token: str) -> tuple[str, str]:
        parts = token.split(".")
        if len(parts) != 3 or not all(parts):
            raise AuthenticationError("token is not a well-formed JWT")
        return parts[0], parts[1]

    def _check_algorithm(self, header_b64: str) -> None:
        try:
            header = json.loads(_b64url_decode(header_b64))
        except (ValueError, TypeError) as exc:
            raise AuthenticationError("malformed token header") from exc
        # Pin the algorithm: reject 'none', 'RS256', anything but HS256.
        if not isinstance(header, dict) or header.get("alg") != _ALGORITHM:
            raise AuthenticationError("unsupported token algorithm")

    def _check_signature(self, signing_input: str, token: str) -> None:
        provided = token.rsplit(".", 1)[1]
        expected = _b64url_encode(
            hmac.new(self._secret, signing_input.encode("ascii"), hashlib.sha256).digest()
        )
        # Constant-time comparison defeats signature-forging timing attacks.
        if not hmac.compare_digest(provided, expected):
            raise AuthenticationError("token signature verification failed")

    def _decode_claims(self, payload_b64: str) -> dict[str, Any]:
        try:
            claims = json.loads(_b64url_decode(payload_b64))
        except (ValueError, TypeError) as exc:
            raise AuthenticationError("malformed token payload") from exc
        if not isinstance(claims, dict):
            raise AuthenticationError("token payload is not an object")
        return claims

    def _check_temporal(self, claims: dict[str, Any]) -> None:
        now = int(self._clock.now().timestamp())
        exp = claims.get("exp")
        if not isinstance(exp, int | float):
            raise AuthenticationError("token missing a valid 'exp' claim")
        if now > exp + self._leeway:
            raise AuthenticationError("token has expired")
        nbf = claims.get("nbf")
        if isinstance(nbf, int | float) and now + self._leeway < nbf:
            raise AuthenticationError("token is not yet valid")

    def _check_issuer_audience(self, claims: dict[str, Any]) -> None:
        if claims.get("iss") != self._issuer:
            raise AuthenticationError("token issuer is not accepted")
        aud = claims.get("aud")
        accepted = aud == self._audience or (isinstance(aud, list) and self._audience in aud)
        if not accepted:
            raise AuthenticationError("token audience is not accepted")

    def _to_auth_context(self, claims: dict[str, Any]) -> AuthContext:
        sub = claims.get("sub")
        tenant_id = claims.get("tenant_id")
        roles = claims.get("roles", [])
        if not isinstance(sub, str) or not sub:
            raise AuthenticationError("token missing 'sub' claim")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise AuthenticationError("token missing 'tenant_id' claim")
        if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
            raise AuthenticationError("token 'roles' claim is malformed")
        try:
            return AuthContext(sub=sub, tenant_id=tenant_id, roles=roles)
        except ValueError as exc:
            # A claim that our domain model rejects (e.g. empty after trimming).
            raise AuthenticationError("token claims failed validation") from exc


def build_token_verifier(*, secret: str, issuer: str, audience: str, clock: Clock) -> TokenVerifier:
    """Construct the Phase-5 HS256 token verifier from settings."""
    return HS256TokenVerifier(secret=secret, issuer=issuer, audience=audience, clock=clock)
