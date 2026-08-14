"""End-to-end tests for the AI endpoints (offline: fake provider + sample corpus).

The app is built from test settings; the sample corpus autoloads at startup, so
retrieval is real. These assert authentication, tenant isolation, and the happy
path of every ``/api/v1/ai`` endpoint.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from complianceiq.composition import build_app
from complianceiq.infrastructure.config.settings import Environment, Settings
from tests.auth_helpers import (
    bearer,
    mint_rs256_token,
    mint_token,
    rsa_public_jwk,
)


def _finding(tenant_id: str = "tenant-a", control_id: str = "PR.AA-01") -> dict[str, Any]:
    """A Finding in wire shape (enum *values*, lowercase)."""
    return {
        "id": "finding-1",
        "tenant_id": tenant_id,
        "resource_id": "arn:aws:iam::acct:user/svc",
        "rule_id": "rule-iam-key-rotation",
        "framework": "nist_csf",
        "control_id": control_id,
        "domain": "iam",
        "status": "fail",
        "severity": "high",
        "evidence": {"expected": "rotation<=90d", "actual": "never"},
        "detected_at": "2026-01-01T00:00:00Z",
    }


# --------------------------------- auth ------------------------------------ #


def test_endpoint_requires_authentication(client: TestClient) -> None:
    r = client.post("/api/v1/ai/enrich", json={"findings": [_finding()]})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_error"


def test_bad_token_is_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/ask",
        json={"question": "hello?"},
        headers=bearer("garbage.token.here"),
    )
    assert r.status_code == 401


def test_cross_tenant_finding_is_blocked(client: TestClient) -> None:
    # Token is for tenant-a; the finding claims tenant-b.
    token = mint_token(tenant_id="tenant-a")
    r = client.post(
        "/api/v1/ai/enrich",
        json={"findings": [_finding(tenant_id="tenant-b")]},
        headers=bearer(token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "tenant_isolation_violation"


# ------------------------------- endpoints --------------------------------- #


def test_enrich_returns_grounded_findings(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/enrich",
        json={"findings": [_finding()]},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["citation_verified"] is True
    assert body[0]["citations"]


def test_ask_returns_grounded_answer(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/ask",
        json={"question": "How should IAM access keys be managed?"},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["abstained"] is False
    assert body["citation_verified"] is True


def test_ask_scopes_retrieval_by_framework(client: TestClient) -> None:
    # The framework filter is accepted and the answer is well-formed. (Graph-level
    # abstention is unit-tested separately, where the corpus can be made empty.)
    r = client.post(
        "/api/v1/ai/ask",
        json={"question": "How is data protected at rest?", "framework": "soc_2"},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"question", "answer", "citations", "citation_verified", "abstained"}
    assert isinstance(body["abstained"], bool)


def test_remediate_is_never_approved(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/remediate",
        json={"finding": _finding()},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    assert r.json()["approved"] is False


def test_correlate_returns_narrative(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/correlate",
        json={"findings": [_finding(), _finding(control_id="PR.AA-02")]},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    assert isinstance(r.json()["narrative"], str)
    assert r.json()["narrative"]


def test_report_drafts_over_enriched_findings(client: TestClient) -> None:
    # First enrich to obtain a valid EnrichedFinding, then report over it.
    enriched = client.post(
        "/api/v1/ai/enrich",
        json={"findings": [_finding()]},
        headers=bearer(mint_token()),
    ).json()
    r = client.post(
        "/api/v1/ai/report",
        json={"findings": enriched},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["finding_count"] == 1
    assert body["severity_breakdown"] == {"high": 1}
    assert body["tenant_id"] == "tenant-a"


def test_map_returns_control_mapping(client: TestClient) -> None:
    # A SOC 2 finding over the (multi-framework) shipped corpus yields cross-
    # framework equivalents.
    r = client.post(
        "/api/v1/ai/map",
        json={"finding": _finding() | {"framework": "soc_2", "control_id": "CC6.1"}},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source_framework"] == "soc_2"
    assert "citation_verified" in body
    assert isinstance(body["mappings"], list)


def test_map_cross_tenant_is_blocked(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/map",
        json={"finding": _finding(tenant_id="tenant-b")},
        headers=bearer(mint_token(tenant_id="tenant-a")),
    )
    assert r.status_code == 403


def test_financial_returns_mad_range(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/financial",
        json={"finding": _finding()},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert int(body["min_mad"]) >= 0
    assert int(body["max_mad"]) >= int(body["min_mad"])
    assert body["finding_id"] == "finding-1"
    assert body["assumptions"]
    assert body["rationale"]


def test_financial_cross_tenant_is_blocked(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/financial",
        json={"finding": _finding(tenant_id="tenant-b")},
        headers=bearer(mint_token(tenant_id="tenant-a")),
    )
    assert r.status_code == 403


def test_validation_error_on_empty_findings(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/enrich",
        json={"findings": []},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# --------------------- Core integration (Phase 6, stub) -------------------- #


def test_enrich_by_ids_fetches_from_core(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/enrich/by-ids",
        json={"finding_ids": ["finding-iam-1"]},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["control_id"] == "PR.AA-01"
    assert body[0]["citation_verified"] is True


def test_enrich_by_ids_unknown_id_is_404(client: TestClient) -> None:
    r = client.post(
        "/api/v1/ai/enrich/by-ids",
        json={"finding_ids": ["nope"]},
        headers=bearer(mint_token()),
    )
    assert r.status_code == 404


def test_enrich_by_ids_cross_tenant_is_not_leaked(client: TestClient) -> None:
    # tenant-b asks for tenant-a's seeded finding → 404, never the data.
    r = client.post(
        "/api/v1/ai/enrich/by-ids",
        json={"finding_ids": ["finding-iam-1"]},
        headers=bearer(mint_token(tenant_id="tenant-b")),
    )
    assert r.status_code == 404


# ----------------------- RS256-wired app (Phase 6) ------------------------- #


def test_app_wired_with_rs256_public_key_accepts_rs256_tokens() -> None:
    # Configuring an RSA public JWK makes the composition root select the RS256
    # verifier; an HS256 token must then be rejected and an RS256 one accepted.
    settings = Settings(
        environment=Environment.LOCAL,
        log_json=False,
        log_level="WARNING",
        jwt_public_key=rsa_public_jwk(),  # type: ignore[arg-type]
    )
    app = build_app(settings)
    with TestClient(app) as c:
        ok = c.post(
            "/api/v1/ai/ask",
            json={"question": "How should IAM access keys be managed?"},
            headers=bearer(mint_rs256_token()),
        )
        assert ok.status_code == 200

        hs = c.post(
            "/api/v1/ai/ask",
            json={"question": "hi"},
            headers=bearer(mint_token()),
        )
        assert hs.status_code == 401
