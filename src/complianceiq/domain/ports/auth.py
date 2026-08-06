"""The :class:`TokenVerifier` port.

The Core Service issues the tenant's JWT; this service only **verifies** it and
projects its trusted claims into an :class:`AuthContext`. Verification is an
external concern (it depends on a signing scheme and a key), so it lives behind a
port: the presentation layer depends on this abstraction, and the composition
root supplies a concrete adapter.

Keeping this a port means the *development* verifier (a symmetric HS256 scheme,
Phase 5) and the *production* verifier (the Core's asymmetric RS256/ES256 public
key, Phase 6) are swappable without touching a single caller.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from complianceiq.domain.entities.auth import AuthContext


class TokenVerifier(ABC):
    """Verifies a bearer token and projects its claims into an ``AuthContext``.

    Implementations must treat the token as untrusted input: validate the
    signature and the standard claims (expiry, issuer, audience) before trusting
    any claim, and never leak the token or a key in an error.
    """

    @abstractmethod
    def verify(self, token: str) -> AuthContext:
        """Verify ``token`` and return the authenticated context.

        Args:
            token: The raw bearer token (no ``Bearer `` prefix).

        Returns:
            The :class:`AuthContext` carrying the verified ``sub``, ``tenant_id``,
            and ``roles``.

        Raises:
            AuthenticationError: If the token is malformed, unsigned, tampered
                with, expired, or issued for a different issuer/audience.
        """
        raise NotImplementedError
