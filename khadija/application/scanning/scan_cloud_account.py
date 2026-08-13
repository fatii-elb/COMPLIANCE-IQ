"""``ScanCloudAccount`` (blueprint §4) — the central Application use case.

Formalizes the informal ``ScanService.run()`` into ``application/``
(blueprint §4's own note: "la migration... formalise, elle ne redessine
pas" — the migration formalizes, it does not redesign). Orchestrates the
Domain; it is not a second Domain — every invariant-bearing decision
(tenant isolation, graph integrity, three-valued rule logic, bounded
scores) is made by Domain code this class calls, never reimplemented
here.

Pipeline (blueprint §4's "Séquence interne", with one explicit
correction applied — see below):

    collect -> verify -> build graph -> evaluate rules
    -> discover attack paths -> [risk enrichment: not wired, see
    application/risk/enrich_risk.py] -> detect drift (if a previous
    snapshot was supplied) -> ScanResult

Blueprint §4's prose lists "calculate risk" before "discover attack
paths", but its own architectural note overrides that ordering
explicitly: "Attack Path avant Risk final" — risk must be computed
*after* attack paths are known, since the CRSF-1.1 formula (§13) takes
attack-path involvement as one of its five factors. This pipeline
follows the note, not the looser prose list. In practice this phase
does not call risk enrichment at all (see Known Limitations), so the
ordering matters primarily for whoever wires it in next.

"correlate findings" (also in §4's prose) appears nowhere else in the
blueprint; the only non-inventing reading is "the findings that came out
of rule evaluation, collected together" — satisfied by construction,
with no separate correlation step.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from application.attack_paths.analyze_attack_paths import AnalyzeAttackPaths
from application.drift.detect_drift import DetectDrift
from application.errors import ResourceCollectionError
from application.graph.build_resource_graph import BuildResourceGraph
from application.rules.evaluate_rules import EvaluateRules
from application.rules.rule_catalog import LoadRuleCatalog
from application.scanning.collector import BaseCollector
from application.scanning.dtos import ScanConfiguration, ScanResult
from domain.drift.models import DriftEvent
from domain.shared.enums import CloudProvider
from domain.shared.identifiers import UNKNOWN_ACCOUNT, TenantId
from domain.shared.temporal import is_timezone_aware
from domain.tenants.isolation import ensure_same_tenant


class ScanCloudAccount:
    """Orchestrates a single tenant-scoped cloud scan."""

    def __init__(self, *, collector: BaseCollector, rule_catalog: LoadRuleCatalog) -> None:
        self._collector = collector
        self._build_graph = BuildResourceGraph()
        self._evaluate_rules = EvaluateRules(rule_catalog)
        self._analyze_attack_paths = AnalyzeAttackPaths()
        self._detect_drift = DetectDrift()

    def run(
        self,
        *,
        tenant_id: TenantId,
        provider: CloudProvider,
        credentials_reference: str,
        scan_configuration: ScanConfiguration,
        scanned_at: datetime,
        previous_snapshot: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> ScanResult:
        self._validate_inputs(credentials_reference=credentials_reference, scanned_at=scanned_at)

        resources = self._collect()
        self._verify_collected_resources(resources, tenant_id=tenant_id, provider=provider)

        graph = self._build_graph.build(tenant_id=tenant_id, resources=resources)

        scan_id = self._derive_scan_id(
            tenant_id=tenant_id, provider=provider, resources=resources, scanned_at=scanned_at
        )

        # `graph` MUST be threaded through: domain.rules.conditions treats a
        # `relationship` condition evaluated without a graph as a caller
        # wiring bug and raises. Omitting it here made every scan whose
        # catalog contains a cross-resource rule fail — which is every real
        # scan since Phase 3B added 7 of them. See
        # docs/architecture/phase-4-persistence-audit.md §1.
        findings = self._evaluate_rules.evaluate(
            tenant_id=tenant_id,
            resources=resources,
            detected_at=scanned_at,
            scan_id=scan_id,
            rule_ids=scan_configuration.rule_ids,
            graph=graph,
        )

        attack_paths = self._analyze_attack_paths.analyze(
            tenant_id=tenant_id, graph=graph, findings=findings
        )

        # Risk enrichment (application/risk/EnrichRisk) is deliberately
        # not invoked here — see module docstring and
        # docs/architecture/phase-2-application.md, Known Limitations.

        drift_events: tuple[DriftEvent, ...] = ()
        if previous_snapshot is not None:
            current_snapshot = {str(r.resource_id): dict(r.attributes) for r in resources}
            drift_events = self._detect_drift.detect(
                tenant_id=tenant_id,
                previous=previous_snapshot,
                current=current_snapshot,
                detected_at=scanned_at,
            )

        return ScanResult(
            scan_id=scan_id,
            tenant_id=tenant_id,
            provider=provider,
            scanned_at=scanned_at,
            resources=resources,
            graph=graph,
            findings=findings,
            attack_paths=attack_paths,
            drift_events=drift_events,
        )

    @staticmethod
    def _derive_scan_id(
        *,
        tenant_id: TenantId,
        provider: CloudProvider,
        resources: tuple,
        scanned_at: datetime,
    ) -> str:
        """``tenant:provider:account:timestamp``.

        The account component is what makes this unique. Without it, two
        scans of two different cloud accounts in the same tenant at the
        same instant produced a byte-identical ``scan_id`` — verified, and
        documented in docs/architecture/phase-4-persistence-audit.md §2.
        That made ``scan_id`` unusable as a persistence key.

        The account is read from the collected resources rather than taken
        as a parameter, so no caller signature changes. Collectors stamp
        every resource with the account/subscription they came from. When
        it is genuinely unknown (e.g. AWS ``sts:GetCallerIdentity`` denied
        — a documented non-fatal case) the literal ``"unknown-account"``
        is used: still not unique across two such accounts, but explicit
        rather than silently absent. Phase 4 does not rely on this string
        for identity — it derives its own scan key from the ScanTarget.
        """

        accounts = sorted({r.account_id for r in resources if r.account_id})
        account = accounts[0] if len(accounts) == 1 else ("mixed" if accounts else UNKNOWN_ACCOUNT)
        return f"{tenant_id!s}:{provider.value}:{account}:{scanned_at.isoformat()}"

    @staticmethod
    def _validate_inputs(*, credentials_reference: str, scanned_at: datetime) -> None:
        if not isinstance(credentials_reference, str) or not credentials_reference.strip():
            raise ValueError("credentials_reference must be a non-blank string")
        if not isinstance(scanned_at, datetime) or not is_timezone_aware(scanned_at):
            raise ValueError("scanned_at must be a timezone-aware datetime")

    def _collect(self) -> tuple:
        try:
            return self._collector.collect()
        except Exception as exc:
            raise ResourceCollectionError(f"resource collection failed: {exc}") from exc

    @staticmethod
    def _verify_collected_resources(resources, *, tenant_id: TenantId, provider: CloudProvider) -> None:
        for resource in resources:
            ensure_same_tenant(tenant_id, resource.tenant_id, context="collected resource")
            if resource.cloud_provider is not provider:
                raise ResourceCollectionError(
                    f"collector returned a {resource.cloud_provider.value} resource "
                    f"during a {provider.value} scan: {resource.resource_id!s}"
                )
