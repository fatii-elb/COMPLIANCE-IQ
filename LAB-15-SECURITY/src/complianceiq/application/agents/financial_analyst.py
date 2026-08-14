"""The Financial Analyst agent — quantifies a finding's exposure in MAD.

Wraps the :class:`FinancialGraph`: given a :class:`Finding`, it returns a
:class:`FinancialRiskAssessment` whose monetary range is computed deterministically
(never by the model) and whose rationale is a grounded narrative. No free tools.
"""

from __future__ import annotations

from complianceiq.application.agents.base import BoundedAgent
from complianceiq.application.graphs.financial import FinancialGraph
from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.registry import ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.financial import FinancialRiskAssessment
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.ports.clock import Clock


class FinancialAnalystAgent(BoundedAgent):
    """Estimates a finding's monetary exposure (deterministic range + narrative)."""

    def __init__(
        self,
        *,
        graph: FinancialGraph,
        registry: ToolRegistry,
        clock: Clock,
        budget: AgentBudget | None = None,
    ) -> None:
        super().__init__(
            name="financial_analyst",
            registry=registry,
            allowed_tools=frozenset(),
            budget=budget,
            clock=clock,
        )
        self._graph = graph

    async def assess(self, finding: Finding, auth: AuthContext) -> FinancialRiskAssessment:
        """Assess ``finding``'s financial exposure in MAD."""
        return await self._graph.run(finding, auth)
