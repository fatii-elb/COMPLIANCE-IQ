#!/usr/bin/env python
"""Evaluate the grounding of the AI's answers over a golden set.

Runs the enrichment capability over a small set of findings whose expected
citations are known, and prints the aggregate grounding metrics (grounded rate,
abstention rate, citation precision/recall). Offline by default (the fake
provider + the bundled corpus), so it runs anywhere and gates quality in CI.

Usage:
    python -m scripts.evaluate_ai
    python -m scripts.evaluate_ai --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from complianceiq.application.evaluation import GroundingEvalCase, GroundingEvaluator
from complianceiq.composition import build_container
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.value_objects.enums import (
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)

_AUTH = AuthContext(sub="evaluator", tenant_id="tenant-eval")


def _finding(finding_id: str, control_id: str, domain: RiskDomain, severity: Severity) -> Finding:
    return Finding(
        id=finding_id,
        tenant_id="tenant-eval",
        resource_id=f"arn:example:{finding_id}",
        rule_id=f"rule-{finding_id}",
        framework=Framework.NIST_CSF,
        control_id=control_id,
        domain=domain,
        status=ComplianceStatus.FAIL,
        severity=severity,
        evidence={"detail": "example evidence"},
        detected_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _golden_set() -> list[GroundingEvalCase]:
    """A small golden set aligned with the bundled NIST corpus controls."""
    return [
        GroundingEvalCase(
            finding=_finding("iam-1", "PR.AA-01", RiskDomain.IAM, Severity.HIGH),
            expected_control_ids=["PR.AA-01"],
        ),
        GroundingEvalCase(
            finding=_finding("data-1", "PR.DS-01", RiskDomain.ENCRYPTION, Severity.HIGH),
            expected_control_ids=["PR.DS-01"],
        ),
        GroundingEvalCase(
            finding=_finding("net-1", "PR.IR-01", RiskDomain.NETWORK, Severity.CRITICAL),
            expected_control_ids=["PR.IR-01"],
        ),
        GroundingEvalCase(
            finding=_finding("log-1", "DE.CM-01", RiskDomain.LOGGING, Severity.MEDIUM),
            expected_control_ids=["DE.CM-01"],
        ),
    ]


async def _run(as_json: bool) -> int:
    container = build_container()

    # Ensure the corpus is loaded (the API does this at startup; the CLI does it here).
    from complianceiq.infrastructure.knowledge import load_corpus

    if await container.knowledge.vector_store.count() == 0:
        documents = load_corpus(container.knowledge.corpus_dir)
        await container.knowledge.ingestion.ingest(documents)

    evaluator = GroundingEvaluator(container.agents.compliance_analyst.analyze)
    metrics = await evaluator.evaluate(_golden_set(), _AUTH)

    if as_json:
        print(json.dumps(metrics.model_dump(), indent=2))
    else:
        print("Grounding evaluation")
        print("--------------------")
        print(f"cases:              {metrics.cases}")
        print(f"grounded rate:      {metrics.grounded_rate:.2%}")
        print(f"abstention rate:    {metrics.abstention_rate:.2%}")
        print(f"citation precision: {metrics.citation_precision:.2%}")
        print(f"citation recall:    {metrics.citation_recall:.2%}")
        print(f"mean citations:     {metrics.mean_citations:.2f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AI answer grounding.")
    parser.add_argument("--json", action="store_true", help="Emit metrics as JSON.")
    args = parser.parse_args()
    return asyncio.run(_run(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
