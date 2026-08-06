"""Shared JWT verification pipeline for the concrete verifiers.

Both the Phase-5 HS256 verifier and the Phase-6 RS256 verifier do the *same*
work — split the token, pin the algorithm, verify the signature, then validate
the standard claims (``exp``/``nbf``/``iss``/``aud``) and project
``sub``/``tenant_id``/``roles`` into an :class:`AuthContext`. Only the signature
step differs (a symmetric HMAC vs. an asymmetric RSA check). This base class owns
everything except that one step, so the two schemes cannot drift in how they
validate claims — the security-relevant part.
"""

from __future__ import annotations

import base64
import binascii
import json
from abc import ABC, abstractmethod
from typing import Any

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import AuthenticationError
from complianceiq.domain.ports.auth import TokenVerifier
from complianceiq.domain.ports.clock import Clock


def b64url_decode(segment: str) -> bytes:
    """Decode a base64url segment, tolerating missing padding."""
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (binascii.Error, ValueError) as exc:
        raise AuthenticationError("malformed token encoding") from exc


def b64url_encode(raw: bytes) -> str:
    """Encode bytes as an unpadded base64url string."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class BaseJwtVerifier(TokenVerifier, ABC):
    """The shared verify pipeline; subclasses supply only the signature check."""

    #: The single algorithm this verifier accepts (pinned — no negotiation).
    expected_algorithm: str

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        clock: Clock,
        leeway_seconds: int = 60,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._clock = clock
        self._leeway = leeway_seconds

    def verify(self, token: str) -> AuthContext:
        """Verify ``token`` end to end and return the authenticated context."""
        header_b64, payload_b64 = self._split(token)
        self._check_algorithm(header_b64)
        signing_input = f"{header_b64}.{payload_b64}"
        signature_b64 = token.rsplit(".", 1)[1]
        self._verify_signature(signing_input, signature_b64)
        claims = self._decode_claims(payload_b64)
        self._check_temporal(claims)
        self._check_issuer_audience(claims)
        return self._to_auth_context(claims)

    # ---------------------------------------------------------- signature hook

    @abstractmethod
    def _verify_signature(self, signing_input: str, signature_b64: str) -> None:
        """Verify the token's signature or raise ``AuthenticationError``."""
        raise NotImplementedError

    # ------------------------------------------------------------ shared steps

    def _split(self, token: str) -> tuple[str, str]:
        parts = token.split(".")
        if len(parts) != 3 or not all(parts):
            raise AuthenticationError("token is not a well-formed JWT")
        return parts[0], parts[1]

    def _check_algorithm(self, header_b64: str) -> None:
        try:
            header = json.loads(b64url_decode(header_b64))
        except (ValueError, TypeError) as exc:
            raise AuthenticationError("malformed token header") from exc
        # Pin the algorithm: reject 'none', a different family, anything but ours.
        if not isinstance(header, dict) or header.get("alg") != self.expected_algorithm:
            raise AuthenticationError("unsupported token algorithm")

    def _decode_claims(self, payload_b64: str) -> dict[str, Any]:
        try:
            claims = json.loads(b64url_decode(payload_b64))
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
            raise AuthenticationError("token claims failed validation") from exc
