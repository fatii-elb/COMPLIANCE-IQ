"""The Report Writer agent — drafts an executive compliance summary.

Wraps the :class:`ReportGraph`: given the tenant's enriched findings, it produces
a :class:`ReportDraft` (factual severity breakdown plus a grounded executive
summary). The audit-ready PDF rendering is a later phase.
"""

from __future__ import annotations

from complianceiq.application.agents.base import BoundedAgent
from complianceiq.application.graphs.report import ReportGraph
from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.registry import ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import EnrichedFinding
from complianceiq.domain.entities.report import ReportDraft
from complianceiq.domain.ports.clock import Clock


class ReportWriterAgent(BoundedAgent):
    """Drafts an executive report over a tenant's enriched findings."""

    def __init__(
        self,
        *,
        graph: ReportGraph,
        registry: ToolRegistry,
        clock: Clock,
        budget: AgentBudget | None = None,
    ) -> None:
        super().__init__(
            name="report_writer",
            registry=registry,
            allowed_tools=frozenset(),
            budget=budget,
            clock=clock,
        )
        self._graph = graph

    async def write(self, findings: list[EnrichedFinding], auth: AuthContext) -> ReportDraft:
        """Draft an executive report over ``findings`` for the caller's tenant."""
        return await self._graph.run(findings, auth)
