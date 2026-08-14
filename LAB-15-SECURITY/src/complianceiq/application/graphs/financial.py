"""Financial graph — a Finding becomes a monetary exposure assessment (MAD).

Flow: ``START → estimate → narrate → END``.

- **estimate** computes the exposure *range* deterministically from the finding's
  severity and domain (:func:`estimate_exposure`) — the numbers are never produced
  by a model.
- **narrate** asks the model to explain that pre-computed range in plain language,
  told explicitly not to invent any figure.

Produces a :class:`FinancialRiskAssessment`; like the report graph, the facts are
computed in code and only the prose is generated.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict, cast
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from complianceiq.application.gateway.ai_gateway import AIGateway, GatewayLogger
from complianceiq.application.graphs._common import (
    NullGraphLogger,
    TraceEvent,
    finding_summary,
    traced_node,
)
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.financial import FinancialRiskAssessment
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.policies.financial_model import ExposureBand, estimate_exposure

_SYSTEM_FINANCIAL = (
    "You are ComplianceIQ explaining a cloud-compliance finding's financial exposure "
    "to a CISO. A deterministic model computed the monetary range; use those exact "
    "figures and never invent, widen, narrow, or add any other amount. Be factual and "
    "state that the range is a planning estimate, not a guaranteed loss."
)


class FinancialState(TypedDict, total=False):
    finding: Finding
    auth: AuthContext
    band: ExposureBand
    assessment: FinancialRiskAssessment
    trace: Annotated[list[TraceEvent], operator.add]


class FinancialGraph:
    """Builds and runs the financial-exposure state graph."""

    def __init__(
        self,
        *,
        gateway: AIGateway,
        prompts: PromptRegistry,
        logger: GatewayLogger | None = None,
        node_timeout_seconds: float = 30.0,
    ) -> None:
        self._gateway = gateway
        self._prompts = prompts
        self._log: GatewayLogger = logger or NullGraphLogger()
        self._timeout = node_timeout_seconds
        self._app = self._build()

    async def _estimate(self, state: dict[str, Any]) -> dict[str, Any]:
        band = estimate_exposure(state["finding"])
        return {"band": band, "_detail": f"{band.min_mad}-{band.max_mad} MAD"}

    async def _narrate(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        auth: AuthContext = state["auth"]
        band: ExposureBand = state["band"]

        range_text = f"{band.min_mad:f} to {band.max_mad:f} MAD"
        rendered, _ = self._prompts.render(
            "financial_rationale",
            {
                "finding": finding_summary(finding),
                "exposure_band": range_text,
                "assumptions": "\n".join(f"- {a}" for a in band.assumptions),
            },
        )
        request = LLMRequest(
            messages=[LLMMessage.system(_SYSTEM_FINANCIAL), LLMMessage.user(rendered)],
            task=TaskClass.REASONING,
            feature="financial",
        )
        completion = await self._gateway.generate(request, auth)
        rationale = completion.text.strip() or (
            f"Estimated exposure for {finding.control_id} is {range_text}, a planning "
            "range derived from the finding's severity and domain."
        )
        assessment = FinancialRiskAssessment(
            finding_id=finding.id,
            min_mad=band.min_mad,
            max_mad=band.max_mad,
            rationale=rationale,
            assumptions=band.assumptions,
        )
        return {"assessment": assessment}

    def _build(self) -> Any:
        graph: StateGraph = StateGraph(FinancialState)
        graph.add_node(
            "estimate",
            traced_node(
                "estimate", self._estimate, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_node(
            "narrate",
            traced_node("narrate", self._narrate, timeout_seconds=self._timeout, logger=self._log),
        )
        graph.add_edge(START, "estimate")
        graph.add_edge("estimate", "narrate")
        graph.add_edge("narrate", END)
        return graph.compile(checkpointer=MemorySaver())

    async def run(self, finding: Finding, auth: AuthContext) -> FinancialRiskAssessment:
        """Assess a finding's monetary exposure (deterministic range + narrative)."""
        final = await self._app.ainvoke(
            {"finding": finding, "auth": auth},
            config={"configurable": {"thread_id": uuid4().hex}},
        )
        return cast(FinancialRiskAssessment, final["assessment"])
