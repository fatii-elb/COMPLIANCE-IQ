"""Tests for the HS256 token verifier — including the security-critical cases.

Covers the happy path plus every rejection: tampered signature, expiry, not-yet-
valid, wrong issuer/audience, the algorithm-confusion ('none') attack, malformed
tokens, and missing/invalid claims.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

import pytest

from complianceiq.domain.exceptions import AuthenticationError, ValidationError
from complianceiq.infrastructure.auth.jwt_verifier import HS256TokenVerifier
from tests.auth_helpers import AUDIENCE, ISSUER, _b64, mint_token
from tests.fakes import MutableClock

SECRET = "unit-test-secret"
_BASE = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp())


def _verifier(clock: MutableClock | None = None) -> HS256TokenVerifier:
    return HS256TokenVerifier(
        secret=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        clock=clock or MutableClock(datetime(2026, 1, 1, tzinfo=UTC)),
    )


def _token(**overrides: object) -> str:
    extra = {"exp": _BASE + 3600}
    extra.update(overrides.pop("extra_claims", {}))  # type: ignore[arg-type]
    return mint_token(secret=SECRET, extra_claims=extra, **overrides)  # type: ignore[arg-type]


def test_valid_token_yields_auth_context() -> None:
    auth = _verifier().verify(_token(sub="svc-1", tenant_id="tenant-x", roles=["admin"]))
    assert auth.sub == "svc-1"
    assert auth.tenant_id == "tenant-x"
    assert auth.roles == ["admin"]


def test_tampered_signature_is_rejected() -> None:
    token = _token()
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(AuthenticationError, match="signature"):
        _verifier().verify(tampered)


def test_wrong_secret_is_rejected() -> None:
    token = mint_token(secret="a-different-secret", extra_claims={"exp": _BASE + 3600})
    with pytest.raises(AuthenticationError, match="signature"):
        _verifier().verify(token)


def test_expired_token_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="expired"):
        _verifier().verify(_token(extra_claims={"exp": _BASE - 3600}))


def test_not_yet_valid_token_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="not yet valid"):
        _verifier().verify(_token(extra_claims={"exp": _BASE + 7200, "nbf": _BASE + 3600}))


def test_wrong_issuer_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="issuer"):
        _verifier().verify(_token(issuer="evil-issuer"))


def test_wrong_audience_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="audience"):
        _verifier().verify(_token(audience="some-other-api"))


def test_algorithm_confusion_none_is_rejected() -> None:
    # An attacker downgrades alg to 'none' hoping we skip signature checks.
    token = mint_token(secret=SECRET, algorithm="none", extra_claims={"exp": _BASE + 3600})
    with pytest.raises(AuthenticationError, match="algorithm"):
        _verifier().verify(token)


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="well-formed"):
        _verifier().verify("not.a.jwt.at.all")
    with pytest.raises(AuthenticationError, match="well-formed"):
        _verifier().verify("onlyonesegment")


def test_missing_tenant_claim_is_rejected() -> None:
    token = mint_token(secret=SECRET, extra_claims={"exp": _BASE + 3600, "tenant_id": ""})
    with pytest.raises(AuthenticationError, match="tenant_id"):
        _verifier().verify(token)


def test_missing_exp_claim_is_rejected() -> None:
    token = mint_token(secret=SECRET, extra_claims={"exp": None})
    with pytest.raises(AuthenticationError, match="exp"):
        _verifier().verify(token)


def test_empty_secret_fails_fast_at_construction() -> None:
    with pytest.raises(ValidationError, match="non-empty secret"):
        HS256TokenVerifier(secret="", issuer=ISSUER, audience=AUDIENCE, clock=MutableClock())


def test_audience_list_is_accepted() -> None:
    token = _token(extra_claims={"exp": _BASE + 3600, "aud": ["other", AUDIENCE]})
    auth = _verifier().verify(token)
    assert auth.tenant_id == "tenant-a"


def test_missing_sub_claim_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="sub"):
        _verifier().verify(_token(extra_claims={"exp": _BASE + 3600, "sub": ""}))


def test_malformed_roles_claim_is_rejected() -> None:
    token = _token(extra_claims={"exp": _BASE + 3600, "roles": [1, 2, 3]})
    with pytest.raises(AuthenticationError, match="roles"):
        _verifier().verify(token)


def test_non_object_payload_is_rejected() -> None:
    # A payload that decodes to a JSON array, not an object.
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(b"[1, 2, 3]")
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = _b64(hmac.new(SECRET.encode(), signing_input, hashlib.sha256).digest())
    with pytest.raises(AuthenticationError, match="not an object"):
        _verifier().verify(f"{header}.{payload}.{sig}")


def test_malformed_base64_payload_is_rejected() -> None:
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = "!!!not-base64!!!"
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = _b64(hmac.new(SECRET.encode(), signing_input, hashlib.sha256).digest())
    with pytest.raises(AuthenticationError):
        _verifier().verify(f"{header}.{payload}.{sig}")
