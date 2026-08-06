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


# --------------------------------------------------------------------------- #
# RS256 test keypair (a small 1024-bit key — for tests only, never production).
# The RS256 verifier only needs the public (n, e); the private d lets tests mint
# tokens with a pure-Python signer, no crypto library required.
# --------------------------------------------------------------------------- #
RSA_N = 106605010057054260756312540863635327074579598779704042478192441570951721583998731244971896283887763134215322255158984167262026949775061235440732782911194758347674999890033714627403368954552763352286164858462692549263565162705092355082859532632251893633447938540247821048798062427949484447838172118875909811211
RSA_D = 32862978442447277569308669348124334542132408168612551233454718663624176131979284485743430743295916483826726208416268018542117131792812642318219088654574778762682743315655301259887738167969121439678570045744688198613025546496167949166910994689942911406284078483981059474715546457903396155900463561184431779401
RSA_E = 65537


def _b64u_int(value: int) -> str:
    return _b64(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def rsa_public_jwk() -> str:
    """The RSA public key as a JWK JSON string (what the verifier consumes)."""
    return json.dumps({"n": _b64u_int(RSA_N), "e": _b64u_int(RSA_E)})


def mint_rs256_token(
    *,
    sub: str = "user-1",
    tenant_id: str = "tenant-a",
    roles: list[str] | None = None,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_in: int = 3600,
    exp: int | None = None,
) -> str:
    """Mint an RS256 JWT signed with the test private key (pure Python)."""
    # DER prefix of the SHA-256 DigestInfo, matching the verifier.
    prefix = bytes(
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
    header_b64 = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims: dict[str, Any] = {
        "sub": sub,
        "tenant_id": tenant_id,
        "roles": roles if roles is not None else ["analyst"],
        "iss": issuer,
        "aud": audience,
        "exp": exp if exp is not None else int(time.time()) + expires_in,
    }
    payload_b64 = _b64(json.dumps(claims).encode())
    key_bytes = (RSA_N.bit_length() + 7) // 8
    digest_info = prefix + hashlib.sha256(f"{header_b64}.{payload_b64}".encode()).digest()
    em = b"\x00\x01" + b"\xff" * (key_bytes - len(digest_info) - 3) + b"\x00" + digest_info
    signature = pow(int.from_bytes(em, "big"), RSA_D, RSA_N)
    sig_b64 = _b64(signature.to_bytes(key_bytes, "big"))
    return f"{header_b64}.{payload_b64}.{sig_b64}"
