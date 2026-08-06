"""An in-process, seeded Core client (offline default).

Mirrors the ``core-stub`` the AI service targets locally: it holds a few sample
findings per tenant so the whole pipeline — fetch → enrich → return — runs with
no live Core Service. It enforces the same **tenant scoping** the real Core does:
a caller only ever sees findings whose ``tenant_id`` matches their ``AuthContext``
(a foreign id reads as "not found," never a cross-tenant leak).
"""

from __future__ import annotations

from datetime import UTC, datetime

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.pagination import Page
from complianceiq.domain.exceptions import NotFoundError
from complianceiq.domain.ports.core import CoreClient
from complianceiq.domain.value_objects.enums import (
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)


def sample_findings(tenant_id: str = "tenant-a") -> list[Finding]:
    """A small, deterministic set of findings for one tenant (dev/testing)."""
    detected = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Finding(
            id="finding-iam-1",
            tenant_id=tenant_id,
            resource_id="arn:aws:iam::acct:user/svc",
            rule_id="rule-iam-key-rotation",
            framework=Framework.NIST_CSF,
            control_id="PR.AA-01",
            domain=RiskDomain.IAM,
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            evidence={"expected": "rotation<=90d", "actual": "never"},
            detected_at=detected,
        ),
        Finding(
            id="finding-net-1",
            tenant_id=tenant_id,
            resource_id="arn:aws:ec2::acct:sg/open",
            rule_id="rule-sg-open-ingress",
            framework=Framework.NIST_CSF,
            control_id="PR.IR-01",
            domain=RiskDomain.NETWORK,
            status=ComplianceStatus.FAIL,
            severity=Severity.CRITICAL,
            evidence={"expected": "no 0.0.0.0/0", "actual": "0.0.0.0/0 on :22"},
            detected_at=detected,
        ),
    ]


class StubCoreClient(CoreClient):
    """A seeded, in-memory Core client for offline development and tests."""

    def __init__(self, findings: list[Finding] | None = None) -> None:
        seed = findings if findings is not None else sample_findings()
        self._by_tenant: dict[str, list[Finding]] = {}
        for finding in seed:
            self._by_tenant.setdefault(finding.tenant_id, []).append(finding)

    async def get_finding(
        self, auth: AuthContext, finding_id: str, *, bearer_token: str
    ) -> Finding:
        for finding in self._by_tenant.get(auth.tenant_id, []):
            if finding.id == finding_id:
                return finding
        # A finding in another tenant reads as absent — never a cross-tenant leak.
        raise NotFoundError(
            "finding not found for tenant",
            details={"finding_id": finding_id},
        )

    async def list_findings(
        self,
        auth: AuthContext,
        *,
        bearer_token: str,
        framework: Framework | None = None,
        severity: Severity | None = None,
        status: ComplianceStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Finding]:
        items = [
            f
            for f in self._by_tenant.get(auth.tenant_id, [])
            if (framework is None or f.framework is framework)
            and (severity is None or f.severity is severity)
            and (status is None or f.status is status)
        ]
        window = items[offset : offset + limit]
        return Page(items=window, total=len(items), limit=limit, offset=offset)
