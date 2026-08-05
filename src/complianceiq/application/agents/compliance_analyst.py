"""The Compliance Analyst agent — explains a finding, grounded and cited.

This agent wraps the :class:`EnrichmentGraph`: given a :class:`Finding`, it
produces a grounded, cited :class:`EnrichedFinding` (or an abstention). It is an
agent (not just a graph call) so the presentation layer has one uniform,
budget-bounded entry point per capability, and so richer tool-using behaviour can
be added later without changing callers.
"""

from __future__ import annotations

from complianceiq.application.agents.base import BoundedAgent
from complianceiq.application.graphs.enrichment import EnrichmentGraph
from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.registry import ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.ports.clock import Clock


class ComplianceAnalystAgent(BoundedAgent):
    """Turns a raw finding into a grounded, cited explanation."""

    def __init__(
        self,
        *,
        graph: EnrichmentGraph,
        registry: ToolRegistry,
        clock: Clock,
        budget: AgentBudget | None = None,
    ) -> None:
        super().__init__(
            name="compliance_analyst",
            registry=registry,
            allowed_tools=frozenset(),  # grounding is via the graph, not free tools
            budget=budget,
            clock=clock,
        )
        self._graph = graph

    async def analyze(self, finding: Finding, auth: AuthContext) -> EnrichedFinding:
        """Explain ``finding`` for the caller's tenant, grounded in the corpus."""
        return await self._graph.run(finding, auth)
