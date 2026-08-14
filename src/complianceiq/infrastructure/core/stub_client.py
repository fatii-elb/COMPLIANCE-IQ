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


def demo_findings(tenant_id: str = "tenant-a") -> list[Finding]:
    """A richer, realistic demo dataset for one tenant (frontend/offline demo).

    A **superset** of :func:`sample_findings` — it keeps the two canonical
    findings (``finding-iam-1``, ``finding-net-1``) so anything relying on those
    ids still works, and adds variety across clouds, frameworks, domains,
    severities, and pass/fail so the dashboard, filters, and charts have real data
    to render with no live Core Service. Deterministic (fixed timestamps).
    """
    base = sample_findings(tenant_id)
    extra = [
        Finding(
            id="finding-storage-1",
            tenant_id=tenant_id,
            resource_id="arn:aws:s3:::acme-public-assets",
            rule_id="rule-s3-public-read",
            framework=Framework.ISO_27001,
            control_id="A.5.10",
            domain=RiskDomain.STORAGE,
            status=ComplianceStatus.FAIL,
            severity=Severity.CRITICAL,
            evidence={"expected": "no public ACL", "actual": "READ granted to AllUsers"},
            detected_at=datetime(2026, 1, 3, 9, 15, tzinfo=UTC),
        ),
        Finding(
            id="finding-enc-1",
            tenant_id=tenant_id,
            resource_id="/subscriptions/xxx/disks/data-01",
            rule_id="rule-disk-unencrypted",
            framework=Framework.ISO_27001,
            control_id="A.8.24",
            domain=RiskDomain.ENCRYPTION,
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            evidence={"expected": "encryption-at-rest", "actual": "disabled"},
            detected_at=datetime(2026, 1, 4, 14, 2, tzinfo=UTC),
        ),
        Finding(
            id="finding-log-1",
            tenant_id=tenant_id,
            resource_id="projects/acme/logs/audit",
            rule_id="rule-audit-logging-off",
            framework=Framework.LOI_05_20,
            control_id="Art.23",
            domain=RiskDomain.LOGGING,
            status=ComplianceStatus.FAIL,
            severity=Severity.MEDIUM,
            evidence={"expected": "admin activity logs on", "actual": "no data-access logs"},
            detected_at=datetime(2026, 1, 5, 11, 40, tzinfo=UTC),
        ),
        Finding(
            id="finding-iam-2",
            tenant_id=tenant_id,
            resource_id="/subscriptions/xxx/users/ops-admin",
            rule_id="rule-mfa-missing",
            framework=Framework.DNSSI,
            control_id="DNSSI-AUTH-02",
            domain=RiskDomain.IAM,
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            evidence={"expected": "MFA enforced", "actual": "MFA not configured"},
            detected_at=datetime(2026, 1, 6, 8, 20, tzinfo=UTC),
        ),
        Finding(
            id="finding-net-2",
            tenant_id=tenant_id,
            resource_id="projects/acme/firewalls/default-allow",
            rule_id="rule-egress-unrestricted",
            framework=Framework.SOC_2,
            control_id="CC6.6",
            domain=RiskDomain.NETWORK,
            status=ComplianceStatus.FAIL,
            severity=Severity.MEDIUM,
            evidence={"expected": "scoped egress", "actual": "0.0.0.0/0 egress all ports"},
            detected_at=datetime(2026, 1, 7, 16, 5, tzinfo=UTC),
        ),
        Finding(
            id="finding-storage-2",
            tenant_id=tenant_id,
            resource_id="projects/acme/buckets/backups",
            rule_id="rule-bucket-versioning-off",
            framework=Framework.ISO_27001,
            control_id="A.8.13",
            domain=RiskDomain.STORAGE,
            status=ComplianceStatus.FAIL,
            severity=Severity.LOW,
            evidence={"expected": "versioning enabled", "actual": "disabled"},
            detected_at=datetime(2026, 1, 8, 10, 0, tzinfo=UTC),
        ),
        Finding(
            id="finding-enc-2",
            tenant_id=tenant_id,
            resource_id="arn:aws:rds:eu-west-1:acct:db/prod",
            rule_id="rule-rds-tls-required",
            framework=Framework.DNSSI,
            control_id="DNSSI-CRY-01",
            domain=RiskDomain.ENCRYPTION,
            status=ComplianceStatus.PASS,
            severity=Severity.LOW,
            evidence={"expected": "TLS required", "actual": "TLS required"},
            detected_at=datetime(2026, 1, 9, 12, 30, tzinfo=UTC),
        ),
        Finding(
            id="finding-log-2",
            tenant_id=tenant_id,
            resource_id="arn:aws:cloudtrail:acct:trail/org",
            rule_id="rule-cloudtrail-enabled",
            framework=Framework.SOC_2,
            control_id="CC7.2",
            domain=RiskDomain.LOGGING,
            status=ComplianceStatus.PASS,
            severity=Severity.LOW,
            evidence={"expected": "multi-region trail", "actual": "multi-region trail on"},
            detected_at=datetime(2026, 1, 10, 9, 45, tzinfo=UTC),
        ),
        Finding(
            id="finding-iam-3",
            tenant_id=tenant_id,
            resource_id="projects/acme/serviceAccounts/ci",
            rule_id="rule-sa-overprivileged",
            framework=Framework.NIST_CSF,
            control_id="PR.AA-05",
            domain=RiskDomain.IAM,
            status=ComplianceStatus.FAIL,
            severity=Severity.HIGH,
            evidence={"expected": "least privilege", "actual": "roles/owner granted"},
            detected_at=datetime(2026, 1, 11, 13, 15, tzinfo=UTC),
        ),
        Finding(
            id="finding-net-3",
            tenant_id=tenant_id,
            resource_id="/subscriptions/xxx/nsg/db-tier",
            rule_id="rule-db-port-public",
            framework=Framework.LOI_05_20,
            control_id="Art.18",
            domain=RiskDomain.NETWORK,
            status=ComplianceStatus.FAIL,
            severity=Severity.MEDIUM,
            evidence={"expected": "no public 5432", "actual": "5432 open to Internet"},
            detected_at=datetime(2026, 1, 12, 15, 50, tzinfo=UTC),
        ),
    ]
    return base + extra


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
