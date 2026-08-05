"""Report graph — enriched findings become an executive report draft.

Flow: ``START → summarize → generate → END``.

- **summarize** computes factual breakdowns (counts per severity) and a compact
  findings digest.
- **generate** writes the executive summary from that digest (grounded in the
  findings, told not to invent anything).

Produces a :class:`ReportDraft`; the audit-ready PDF rendering is a later phase.
"""

from __future__ import annotations

import operator
from collections import Counter
from typing import Annotated, Any, TypedDict, cast
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from complianceiq.application.gateway.ai_gateway import AIGateway, GatewayLogger
from complianceiq.application.graphs._common import NullGraphLogger, TraceEvent, traced_node
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import EnrichedFinding
from complianceiq.domain.entities.report import ReportDraft
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.ports.clock import Clock

_SYSTEM_REPORT = (
    "You are ComplianceIQ writing an executive compliance summary for a CISO. Use "
    "ONLY the findings provided. Do not invent findings, controls, or figures. Be "
    "factual and audit-appropriate."
)


class ReportState(TypedDict, total=False):
    findings: list[EnrichedFinding]
    auth: AuthContext
    tenant_id: str
    digest: str
    severity_breakdown: dict[str, int]
    draft: ReportDraft
    trace: Annotated[list[TraceEvent], operator.add]


class ReportGraph:
    """Builds and runs the report-drafting state graph."""

    def __init__(
        self,
        *,
        gateway: AIGateway,
        prompts: PromptRegistry,
        clock: Clock,
        logger: GatewayLogger | None = None,
        node_timeout_seconds: float = 30.0,
    ) -> None:
        self._gateway = gateway
        self._prompts = prompts
        self._clock = clock
        self._log: GatewayLogger = logger or NullGraphLogger()
        self._timeout = node_timeout_seconds
        self._app = self._build()

    async def _summarize(self, state: dict[str, Any]) -> dict[str, Any]:
        findings: list[EnrichedFinding] = state["findings"]
        breakdown = dict(Counter(f.severity.value for f in findings))
        if findings:
            lines = [
                f"- [{f.severity.value}] {f.framework.value} {f.control_id} "
                f"({f.domain.value}): {f.explanation[:160]}"
                for f in findings
            ]
            digest = "\n".join(lines)
        else:
            digest = "No findings were reported."
        return {"digest": digest, "severity_breakdown": breakdown}

    async def _generate(self, state: dict[str, Any]) -> dict[str, Any]:
        auth: AuthContext = state["auth"]
        findings: list[EnrichedFinding] = state["findings"]

        rendered, _ = self._prompts.render("report_summary", {"findings_summary": state["digest"]})
        request = LLMRequest(
            messages=[LLMMessage.system(_SYSTEM_REPORT), LLMMessage.user(rendered)],
            task=TaskClass.REASONING,
            feature="report",
        )
        completion = await self._gateway.generate(request, auth)
        draft = ReportDraft(
            tenant_id=state["tenant_id"],
            executive_summary=completion.text.strip() or "No findings to report.",
            finding_count=len(findings),
            severity_breakdown=state["severity_breakdown"],
            generated_at=self._clock.now(),
        )
        return {"draft": draft}

    def _build(self) -> Any:
        graph: StateGraph = StateGraph(ReportState)
        graph.add_node(
            "summarize",
            traced_node(
                "summarize", self._summarize, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_node(
            "generate",
            traced_node(
                "generate", self._generate, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_edge(START, "summarize")
        graph.add_edge("summarize", "generate")
        graph.add_edge("generate", END)
        return graph.compile(checkpointer=MemorySaver())

    async def run(self, findings: list[EnrichedFinding], auth: AuthContext) -> ReportDraft:
        """Draft an executive report over ``findings`` for the caller's tenant."""
        final = await self._app.ainvoke(
            {"findings": findings, "auth": auth, "tenant_id": auth.tenant_id},
            config={"configurable": {"thread_id": uuid4().hex}},
        )
        return cast(ReportDraft, final["draft"])
