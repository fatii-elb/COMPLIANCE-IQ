"""The Control Mapper agent — maps a finding's control across frameworks.

Wraps the :class:`MappingGraph`: given a :class:`Finding`, it produces a grounded
:class:`ControlMapping` of equivalent controls in other frameworks (or an
abstention). No free tools — the grounding comes from the graph.
"""

from __future__ import annotations

from complianceiq.application.agents.base import BoundedAgent
from complianceiq.application.graphs.mapping import MappingGraph
from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.registry import ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.mapping import ControlMapping
from complianceiq.domain.ports.clock import Clock


class ControlMapperAgent(BoundedAgent):
    """Maps a finding's control to equivalent controls across frameworks."""

    def __init__(
        self,
        *,
        graph: MappingGraph,
        registry: ToolRegistry,
        clock: Clock,
        budget: AgentBudget | None = None,
    ) -> None:
        super().__init__(
            name="control_mapper",
            registry=registry,
            allowed_tools=frozenset(),
            budget=budget,
            clock=clock,
        )
        self._graph = graph

    async def map(self, finding: Finding, auth: AuthContext) -> ControlMapping:
        """Map ``finding``'s control to equivalent controls in other frameworks."""
        return await self._graph.run(finding, auth)
