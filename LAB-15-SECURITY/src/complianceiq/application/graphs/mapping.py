"""Mapping graph — a Finding's control becomes cross-framework equivalents.

Flow: ``START → retrieve → (context empty?) ─yes→ abstain → END``; otherwise
``→ map → END``. Same grounding discipline as enrichment: equivalences are drawn
only from retrieved, verified controls in *other* frameworks — never invented —
and an empty retrieval abstains without calling the model. Produces a
:class:`ControlMapping`.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict, cast
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from complianceiq.application.gateway.ai_gateway import AIGateway, GatewayLogger
from complianceiq.application.graphs._common import (
    SYSTEM_GROUNDED,
    NullGraphLogger,
    TraceEvent,
    finding_summary,
    retrieve_and_assemble,
    traced_node,
)
from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.mapping import ControlMapping, MappedControl
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT, verify_citations
from complianceiq.domain.policies.prompt_safety import wrap_untrusted


class MappingState(TypedDict, total=False):
    finding: Finding
    auth: AuthContext
    context: Any  # AssembledContext
    mapping: ControlMapping
    trace: Annotated[list[TraceEvent], operator.add]


class MappingGraph:
    """Builds and runs the cross-framework control-mapping state graph."""

    def __init__(
        self,
        *,
        retriever: HybridRetriever,
        assembler: ContextAssembler,
        gateway: AIGateway,
        prompts: PromptRegistry,
        config: RetrievalConfig,
        logger: GatewayLogger | None = None,
        node_timeout_seconds: float = 30.0,
    ) -> None:
        self._retriever = retriever
        self._assembler = assembler
        self._gateway = gateway
        self._prompts = prompts
        self._config = config
        self._log: GatewayLogger = logger or NullGraphLogger()
        self._timeout = node_timeout_seconds
        self._app = self._build()

    async def _retrieve(self, state: dict[str, Any]) -> dict[str, Any]:
        _, context = await retrieve_and_assemble(
            self._retriever,
            self._assembler,
            query_text=finding_summary(state["finding"]),
            top_k=self._config.rerank_top_k,
            token_budget=self._config.context_token_budget,
        )
        return {"context": context, "_detail": f"{len(context.chunk_ids)} chunks"}

    async def _map(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        auth: AuthContext = state["auth"]
        context = state["context"]

        source_control = f"{finding.framework.value} {finding.control_id}"
        rendered, _ = self._prompts.render(
            "control_mapping",
            {
                "finding": finding_summary(finding),
                "source_control": source_control,
                "context": wrap_untrusted(context.text),
            },
        )
        request = LLMRequest(
            messages=[LLMMessage.system(SYSTEM_GROUNDED), LLMMessage.user(rendered)],
            task=TaskClass.REASONING,
            feature="map",
        )
        completion = await self._gateway.generate(request, auth)

        verification = verify_citations(context.citations, context.citations)
        # Equivalents are verified controls in a *different* framework than the source.
        mappings = [
            MappedControl(
                framework=citation.framework,
                control_id=citation.control_id,
                reference=citation.reference,
            )
            for citation in verification.verified
            if citation.framework is not finding.framework
        ]
        mapping = ControlMapping(
            finding_id=finding.id,
            source_framework=finding.framework,
            source_control_id=finding.control_id,
            summary=completion.text.strip() or ABSTENTION_TEXT,
            mappings=mappings,
            citations=verification.verified,
            citation_verified=verification.all_verified and not context.is_empty,
        )
        return {"mapping": mapping}

    async def _abstain(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        mapping = ControlMapping(
            finding_id=finding.id,
            source_framework=finding.framework,
            source_control_id=finding.control_id,
            summary=ABSTENTION_TEXT,
            mappings=[],
            citations=[],
            citation_verified=False,
        )
        return {"mapping": mapping}

    def _route(self, state: dict[str, Any]) -> str:
        return "abstain" if state["context"].is_empty else "map"

    def _build(self) -> Any:
        graph: StateGraph = StateGraph(MappingState)
        graph.add_node(
            "retrieve",
            traced_node(
                "retrieve", self._retrieve, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_node(
            "map", traced_node("map", self._map, timeout_seconds=self._timeout, logger=self._log)
        )
        graph.add_node(
            "abstain",
            traced_node("abstain", self._abstain, timeout_seconds=self._timeout, logger=self._log),
        )
        graph.add_edge(START, "retrieve")
        graph.add_conditional_edges("retrieve", self._route, {"map": "map", "abstain": "abstain"})
        graph.add_edge("map", END)
        graph.add_edge("abstain", END)
        return graph.compile(checkpointer=MemorySaver())

    async def run(self, finding: Finding, auth: AuthContext) -> ControlMapping:
        """Map a finding's control to equivalent controls across frameworks."""
        final = await self._app.ainvoke(
            {"finding": finding, "auth": auth},
            config={"configurable": {"thread_id": uuid4().hex}},
        )
        return cast(ControlMapping, final["mapping"])
