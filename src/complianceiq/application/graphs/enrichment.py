"""Enrichment graph — a Finding becomes a grounded, cited EnrichedFinding.

Flow:

```
START → retrieve → (context empty?) ─yes→ abstain → END
                        │no
                        └─────────────→ generate → END
```

- **retrieve** fetches relevant controls and assembles a cited context block.
- If nothing relevant was retrieved, **abstain** returns the "not covered"
  answer (grounding rule 3) — no model call.
- Otherwise **generate** produces the explanation from the fenced context and
  attaches only *verified* citations.

Modelling this as an explicit graph makes the abstain branch a first-class edge
(not a buried ``if``), makes every node independently testable, and emits a trace
of the run.
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
    traced_node,
)
from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import EnrichedFinding, Finding
from complianceiq.domain.knowledge.queries import RetrievalQuery
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT, verify_citations
from complianceiq.domain.policies.prompt_safety import wrap_untrusted


class EnrichmentState(TypedDict, total=False):
    """Typed state threaded through the enrichment graph."""

    finding: Finding
    auth: AuthContext
    result: Any  # RetrievalResult
    context: Any  # AssembledContext
    enriched: EnrichedFinding
    trace: Annotated[list[TraceEvent], operator.add]


class EnrichmentGraph:
    """Builds and runs the finding-enrichment state graph."""

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

    # ------------------------------------------------------------------ nodes

    async def _retrieve(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        query = RetrievalQuery(text=finding_summary(finding), top_k=self._config.rerank_top_k)
        result = await self._retriever.retrieve(query)
        context = self._assembler.assemble(result, token_budget=self._config.context_token_budget)
        return {"result": result, "context": context, "_detail": f"{len(result.chunks)} chunks"}

    async def _generate(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        auth: AuthContext = state["auth"]
        context = state["context"]

        rendered, _ = self._prompts.render(
            "enrich_finding",
            {"finding": finding_summary(finding), "context": wrap_untrusted(context.text)},
        )
        request = LLMRequest(
            messages=[LLMMessage.system(SYSTEM_GROUNDED), LLMMessage.user(rendered)],
            task=TaskClass.REASONING,
            feature="enrich",
        )
        completion = await self._gateway.generate(request, auth)

        # Attach only citations verified against the retrieved sources.
        verification = verify_citations(context.citations, context.citations)
        enriched = EnrichedFinding(
            **finding.model_dump(),
            explanation=completion.text.strip() or ABSTENTION_TEXT,
            citations=verification.verified,
            citation_verified=verification.all_verified and not context.is_empty,
        )
        return {"enriched": enriched}

    async def _abstain(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        enriched = EnrichedFinding(
            **finding.model_dump(),
            explanation=ABSTENTION_TEXT,
            citations=[],
            citation_verified=False,
        )
        return {"enriched": enriched}

    def _route(self, state: dict[str, Any]) -> str:
        return "abstain" if state["context"].is_empty else "generate"

    # ------------------------------------------------------------------ build

    def _build(self) -> Any:
        graph: StateGraph = StateGraph(EnrichmentState)
        graph.add_node(
            "retrieve",
            traced_node(
                "retrieve", self._retrieve, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_node(
            "generate",
            traced_node(
                "generate", self._generate, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_node(
            "abstain",
            traced_node("abstain", self._abstain, timeout_seconds=self._timeout, logger=self._log),
        )
        graph.add_edge(START, "retrieve")
        graph.add_conditional_edges(
            "retrieve", self._route, {"generate": "generate", "abstain": "abstain"}
        )
        graph.add_edge("generate", END)
        graph.add_edge("abstain", END)
        return graph.compile(checkpointer=MemorySaver())

    # ------------------------------------------------------------------- run

    async def run(self, finding: Finding, auth: AuthContext) -> EnrichedFinding:
        """Enrich a single finding, returning a grounded :class:`EnrichedFinding`."""
        final = await self._app.ainvoke(
            {"finding": finding, "auth": auth},
            config={"configurable": {"thread_id": uuid4().hex}},
        )
        return cast(EnrichedFinding, final["enriched"])
