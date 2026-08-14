"""Tests for the RS256 (asymmetric) token verifier.

Uses a small test RSA keypair: the verifier gets the public JWK, tests mint tokens
with the private key via a pure-Python signer (no crypto library). Covers the
happy path plus forgery, wrong-key, algorithm pinning, and claim rejections. The
shared claim pipeline (exp/nbf/iss/aud) is covered by the HS256 tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from complianceiq.domain.exceptions import AuthenticationError, ValidationError
from complianceiq.infrastructure.auth.rs256_verifier import (
    RS256TokenVerifier,
    looks_like_jwk,
)
from tests.auth_helpers import (
    AUDIENCE,
    ISSUER,
    mint_rs256_token,
    mint_token,
    rsa_public_jwk,
)
from tests.fakes import MutableClock

_BASE = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())


def _verifier() -> RS256TokenVerifier:
    return RS256TokenVerifier(
        public_key_jwk=rsa_public_jwk(),
        issuer=ISSUER,
        audience=AUDIENCE,
        clock=MutableClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )


def test_valid_rs256_token_yields_auth_context() -> None:
    token = mint_rs256_token(sub="svc-1", tenant_id="tenant-x", roles=["admin"], exp=_BASE + 3600)
    auth = _verifier().verify(token)
    assert auth.sub == "svc-1"
    assert auth.tenant_id == "tenant-x"
    assert auth.roles == ["admin"]


def test_tampered_payload_is_rejected() -> None:
    token = mint_rs256_token(tenant_id="tenant-a", exp=_BASE + 3600)
    header, _payload, sig = token.split(".")
    # Swap in a different (validly-encoded) payload but keep the old signature.
    forged_payload = mint_rs256_token(tenant_id="tenant-evil", exp=_BASE + 3600).split(".")[1]
    with pytest.raises(AuthenticationError, match="signature"):
        _verifier().verify(f"{header}.{forged_payload}.{sig}")


def test_hs256_token_is_rejected_by_rs256_verifier() -> None:
    # Algorithm confusion: an HS256 token must not pass an RS256 verifier.
    token = mint_token(extra_claims={"exp": _BASE + 3600})
    with pytest.raises(AuthenticationError, match="algorithm"):
        _verifier().verify(token)


def test_expired_rs256_token_is_rejected() -> None:
    token = mint_rs256_token(exp=_BASE - 3600)
    with pytest.raises(AuthenticationError, match="expired"):
        _verifier().verify(token)


def test_wrong_issuer_is_rejected() -> None:
    token = mint_rs256_token(issuer="evil-issuer", exp=_BASE + 3600)
    with pytest.raises(AuthenticationError, match="issuer"):
        _verifier().verify(token)


def test_garbage_signature_is_rejected() -> None:
    token = mint_rs256_token(exp=_BASE + 3600)
    header, payload_b64, _ = token.split(".")
    with pytest.raises(AuthenticationError):
        _verifier().verify(f"{header}.{payload_b64}.AAAABBBBCCCC")


def test_invalid_jwk_fails_fast() -> None:
    with pytest.raises(ValidationError, match="JWK"):
        RS256TokenVerifier(
            public_key_jwk="not-json",
            issuer=ISSUER,
            audience=AUDIENCE,
            clock=MutableClock(),
        )


def test_looks_like_jwk() -> None:
    assert looks_like_jwk(rsa_public_jwk()) is True
    assert looks_like_jwk("") is False
    assert looks_like_jwk("plain-secret") is False
    assert looks_like_jwk('{"foo": "bar"}') is False
