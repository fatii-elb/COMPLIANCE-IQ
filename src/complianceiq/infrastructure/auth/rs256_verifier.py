"""A dependency-free RS256 JWT verifier (Phase 6).

Production tokens are signed **asymmetrically** by the Core Service: it signs with
its private key and gives us only its *public* key, so we can verify but never
mint. This adapter verifies RS256 (RSASSA-PKCS1-v1_5 over SHA-256) using nothing
but the Python standard library — because the environment's compiled crypto stack
(``cryptography``/OpenSSL) is unavailable, and RSA *verification* is a short,
well-specified integer computation we can do directly and test offline.

The public key is supplied as a **JWK** (JSON Web Key): ``{"n": <base64url>,
"e": <base64url>}`` — exactly what a JWKS endpoint serves. RSA signature
verification is: interpret the signature as an integer ``s``, compute
``m = s ** e mod n``, and check that ``m`` equals the PKCS#1 v1.5 encoding of the
SHA-256 digest of the signing input. Any mismatch → the token is forged.

Security notes:
- The algorithm is pinned to ``RS256`` (shared base class), closing the ``none``
  downgrade and the RS↔HS confusion attack.
- The reconstructed PKCS#1 block is compared in constant time.
- Claim validation (``exp``/``nbf``/``iss``/``aud``, tenant projection) is the
  exact same shared pipeline the HS256 verifier uses.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from complianceiq.domain.exceptions import AuthenticationError, ValidationError
from complianceiq.domain.ports.auth import TokenVerifier
from complianceiq.domain.ports.clock import Clock
from complianceiq.infrastructure.auth.jwt_base import BaseJwtVerifier, b64url_decode

# DER prefix of the SHA-256 DigestInfo (RFC 8017 §9.2). Prepended to the raw
# 32-byte digest to form the "T" of the EMSA-PKCS1-v1_5 encoding.
_SHA256_DIGESTINFO_PREFIX = bytes(
    (
        0x30,
        0x31,
        0x30,
        0x0D,
        0x06,
        0x09,
        0x60,
        0x86,
        0x48,
        0x01,
        0x65,
        0x03,
        0x04,
        0x02,
        0x01,
        0x05,
        0x00,
        0x04,
        0x20,
    )
)


def _int_from_b64url(segment: str) -> int:
    return int.from_bytes(b64url_decode(segment), "big")


class RS256TokenVerifier(BaseJwtVerifier):
    """Verify RS256-signed JWTs against the Core's RSA public key (JWK)."""

    expected_algorithm = "RS256"

    def __init__(
        self,
        *,
        public_key_jwk: str,
        issuer: str,
        audience: str,
        clock: Clock,
        leeway_seconds: int = 60,
    ) -> None:
        super().__init__(
            issuer=issuer, audience=audience, clock=clock, leeway_seconds=leeway_seconds
        )
        self._n, self._e = self._parse_jwk(public_key_jwk)
        self._key_bytes = (self._n.bit_length() + 7) // 8

    @staticmethod
    def _parse_jwk(public_key_jwk: str) -> tuple[int, int]:
        """Parse an RSA public JWK ``{"n":…, "e":…}`` into (modulus, exponent)."""
        try:
            jwk = json.loads(public_key_jwk)
            modulus = _int_from_b64url(jwk["n"])
            exponent = _int_from_b64url(jwk["e"])
        except (ValueError, TypeError, KeyError, AuthenticationError) as exc:
            raise ValidationError("invalid RSA public JWK for the RS256 verifier") from exc
        if modulus <= 0 or exponent <= 0:
            raise ValidationError("RSA public JWK has a non-positive modulus/exponent")
        return modulus, exponent

    def _emsa_pkcs1_v15(self, message: bytes) -> bytes:
        """Build the expected EMSA-PKCS1-v1_5 encoded message for ``message``."""
        digest_info = _SHA256_DIGESTINFO_PREFIX + hashlib.sha256(message).digest()
        # EM = 0x00 || 0x01 || PS(0xFF…) || 0x00 || T, padded to the key size.
        padding_len = self._key_bytes - len(digest_info) - 3
        if padding_len < 8:
            raise AuthenticationError("RSA key too small for RS256")
        return b"\x00\x01" + b"\xff" * padding_len + b"\x00" + digest_info

    def _verify_signature(self, signing_input: str, signature_b64: str) -> None:
        signature = b64url_decode(signature_b64)
        s = int.from_bytes(signature, "big")
        if s >= self._n:
            raise AuthenticationError("token signature out of range")
        # RSA verification: m = s^e mod n, compared to the PKCS#1 v1.5 encoding.
        m = pow(s, self._e, self._n)
        recovered = m.to_bytes(self._key_bytes, "big")
        expected = self._emsa_pkcs1_v15(signing_input.encode("ascii"))
        if not hmac.compare_digest(recovered, expected):
            raise AuthenticationError("token signature verification failed")


def build_rs256_verifier(
    *, public_key_jwk: str, issuer: str, audience: str, clock: Clock
) -> TokenVerifier:
    """Construct the RS256 token verifier from the Core's public JWK."""
    return RS256TokenVerifier(
        public_key_jwk=public_key_jwk, issuer=issuer, audience=audience, clock=clock
    )


def looks_like_jwk(value: Any) -> bool:
    """Return whether ``value`` is a JSON object string with RSA JWK fields."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = json.loads(value)
    except ValueError:
        return False
    return isinstance(parsed, dict) and "n" in parsed and "e" in parsed
