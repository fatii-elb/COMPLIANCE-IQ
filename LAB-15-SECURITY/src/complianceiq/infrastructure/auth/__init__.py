"""Authentication adapters — concrete :class:`TokenVerifier` implementations.

- :class:`HS256TokenVerifier` — symmetric (shared secret); dev/testing (Phase 5).
- :class:`RS256TokenVerifier` — asymmetric (Core's public JWK); production (Phase 6).

Both share the claim-validation pipeline in :mod:`jwt_base`; the composition root
selects between them via :func:`build_verifier_from_settings`.
"""

from complianceiq.infrastructure.auth.jwt_verifier import (
    HS256TokenVerifier,
    build_token_verifier,
)
from complianceiq.infrastructure.auth.rs256_verifier import (
    RS256TokenVerifier,
    build_rs256_verifier,
    looks_like_jwk,
)

__all__ = [
    "HS256TokenVerifier",
    "RS256TokenVerifier",
    "build_rs256_verifier",
    "build_token_verifier",
    "looks_like_jwk",
]
