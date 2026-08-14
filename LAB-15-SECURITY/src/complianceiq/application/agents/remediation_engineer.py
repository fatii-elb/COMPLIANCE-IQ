"""The Remediation Engineer agent — proposes a never-applied fix.

Wraps the :class:`RemediationGraph`. The resulting :class:`RemediationProposal`
always has ``approved=False`` (non-negotiable rule 2): this agent *proposes*
infrastructure-as-code, statically validated for over-permissive patterns, and a
human disposes. It never touches a customer environment.
"""

from __future__ import annotations

from complianceiq.application.agents.base import BoundedAgent
from complianceiq.application.graphs.remediation import RemediationGraph
from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.registry import ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.remediation import RemediationProposal
from complianceiq.domain.ports.clock import Clock


class RemediationEngineerAgent(BoundedAgent):
    """Proposes a validated, never-applied remediation for a finding."""

    def __init__(
        self,
        *,
        graph: RemediationGraph,
        registry: ToolRegistry,
        clock: Clock,
        budget: AgentBudget | None = None,
    ) -> None:
        super().__init__(
            name="remediation_engineer",
            registry=registry,
            allowed_tools=frozenset(),
            budget=budget,
            clock=clock,
        )
        self._graph = graph

    async def propose(self, finding: Finding, auth: AuthContext) -> RemediationProposal:
        """Propose a remediation for ``finding`` (never applied; needs approval)."""
        return await self._graph.run(finding, auth)
