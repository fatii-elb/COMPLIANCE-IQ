"""``AnalyzeAttackPaths`` (blueprint §4).

KNOWN LIMITATION — read before extending this file: blueprint §11 names
five CURRENT components (``PathDiscovery``, ``PathConstraintEvaluator``,
``AttackPathScorer``, ``AttackTechniqueMapper``, ``AttackPathAnalyzer``)
but specifies no traversal algorithm, no constraint model, and no
scoring formula for any of them — unlike ``RiskScore``, which gets an
exact weighted formula in §13. The Phase 1 audit already flagged this as
a genuine blueprint gap. Fabricating a graph-traversal algorithm here
(e.g. "walk every path to a `PUBLICLY_EXPOSED` node") would mean
inventing business logic — specifically security-relevant business
logic — with no specification to validate it against.

This class exists so ``ScanCloudAccount``'s pipeline shape matches the
blueprint's declared sequence ("discover attack paths" is a real step)
without pretending a discovery algorithm exists. It always returns an
empty tuple. When the blueprint (or a future decision) specifies the
actual algorithm, this is the file to change — its signature already
receives everything a real implementation would need (the tenant-scoped
graph and the findings from this scan).
"""

from __future__ import annotations

from typing import Sequence

from domain.attack_paths.models import AttackPath
from domain.findings.models import Finding
from domain.graph.models import ResourceGraph
from domain.shared.identifiers import TenantId


class AnalyzeAttackPaths:
    """Placeholder orchestration point for attack path discovery. See
    module docstring — no algorithm is implemented.
    """

    def analyze(
        self,
        *,
        tenant_id: TenantId,
        graph: ResourceGraph,
        findings: Sequence[Finding],
    ) -> tuple[AttackPath, ...]:
        return ()
