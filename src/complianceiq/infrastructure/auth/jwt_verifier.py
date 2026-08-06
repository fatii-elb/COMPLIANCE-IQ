"""A dependency-free HS256 JWT verifier (Phase 5).

This adapter implements the :class:`TokenVerifier` port using **HMAC-SHA256**
(HS256), a symmetric JWT scheme, with nothing but the Python standard library —
no crypto packages, no cffi. The shared claim-validation pipeline lives in
:class:`BaseJwtVerifier`; this class supplies only the signature check.

Why HS256 here, RS256 later? HS256 is a legitimate, secure choice for local
development and offline testing (a shared secret both mints and verifies). The
Core Service signs real tokens **asymmetrically** (RS256), and the Phase-6
:class:`~complianceiq.infrastructure.auth.rs256_verifier.RS256TokenVerifier`
verifies those with the Core's public key — same port, same pipeline, so no
caller changes.

Security notes:
- The algorithm is pinned to ``HS256``. A token whose header says ``none`` or
  ``RS256`` is rejected — closing the classic *algorithm-confusion* / downgrade
  attack.
- Signature comparison uses :func:`hmac.compare_digest` (constant time).
- Errors never echo the token, the secret, or the computed signature.
"""

from __future__ import annotations

import hashlib
import hmac

from complianceiq.domain.exceptions import AuthenticationError, ValidationError
from complianceiq.domain.ports.auth import TokenVerifier
from complianceiq.domain.ports.clock import Clock
from complianceiq.infrastructure.auth.jwt_base import BaseJwtVerifier, b64url_encode


class HS256TokenVerifier(BaseJwtVerifier):
    """Verify HS256-signed JWTs against a shared secret (Phase 5)."""

    expected_algorithm = "HS256"

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
        super().__init__(
            issuer=issuer, audience=audience, clock=clock, leeway_seconds=leeway_seconds
        )
        self._secret = secret.encode("utf-8")

    def _verify_signature(self, signing_input: str, signature_b64: str) -> None:
        expected = b64url_encode(
            hmac.new(self._secret, signing_input.encode("ascii"), hashlib.sha256).digest()
        )
        # Constant-time comparison defeats signature-forging timing attacks.
        if not hmac.compare_digest(signature_b64, expected):
            raise AuthenticationError("token signature verification failed")


def build_token_verifier(*, secret: str, issuer: str, audience: str, clock: Clock) -> TokenVerifier:
    """Construct the HS256 token verifier (development / testing)."""
    return HS256TokenVerifier(secret=secret, issuer=issuer, audience=audience, clock=clock)
