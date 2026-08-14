"""Copilot graph — a natural-language question becomes a grounded answer.

Flow: ``START → retrieve → (empty?) → abstain | answer → END``. Same grounding
discipline as enrichment: answer only from retrieved sources, cite them, or
abstain. The output is a :class:`CopilotAnswer`.
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
    retrieve_and_assemble,
    traced_node,
)
from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.copilot import CopilotAnswer
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.policies.grounding import ABSTENTION_TEXT, verify_citations
from complianceiq.domain.policies.prompt_safety import wrap_untrusted


class CopilotState(TypedDict, total=False):
    question: str
    auth: AuthContext
    filter: MetadataFilter
    context: Any  # AssembledContext
    answer: CopilotAnswer
    trace: Annotated[list[TraceEvent], operator.add]


class CopilotGraph:
    """Builds and runs the copilot Q&A state graph."""

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
            query_text=state["question"],
            top_k=self._config.rerank_top_k,
            token_budget=self._config.context_token_budget,
            metadata_filter=state.get("filter"),
        )
        return {"context": context, "_detail": f"{len(context.chunk_ids)} chunks"}

    async def _respond(self, state: dict[str, Any]) -> dict[str, Any]:
        question: str = state["question"]
        auth: AuthContext = state["auth"]
        context = state["context"]

        rendered, _ = self._prompts.render(
            "copilot_answer",
            {"question": question, "context": wrap_untrusted(context.text)},
        )
        request = LLMRequest(
            messages=[LLMMessage.system(SYSTEM_GROUNDED), LLMMessage.user(rendered)],
            task=TaskClass.REASONING,
            feature="copilot",
        )
        completion = await self._gateway.generate(request, auth)
        verification = verify_citations(context.citations, context.citations)
        answer = CopilotAnswer(
            question=question,
            answer=completion.text.strip() or ABSTENTION_TEXT,
            citations=verification.verified,
            citation_verified=verification.all_verified and not context.is_empty,
            abstained=False,
        )
        return {"answer": answer}

    async def _abstain(self, state: dict[str, Any]) -> dict[str, Any]:
        answer = CopilotAnswer(
            question=state["question"],
            answer=ABSTENTION_TEXT,
            citations=[],
            citation_verified=False,
            abstained=True,
        )
        return {"answer": answer}

    def _route(self, state: dict[str, Any]) -> str:
        return "abstain" if state["context"].is_empty else "respond"

    def _build(self) -> Any:
        graph: StateGraph = StateGraph(CopilotState)
        graph.add_node(
            "retrieve",
            traced_node(
                "retrieve", self._retrieve, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_node(
            "respond",
            traced_node("respond", self._respond, timeout_seconds=self._timeout, logger=self._log),
        )
        graph.add_node(
            "abstain",
            traced_node("abstain", self._abstain, timeout_seconds=self._timeout, logger=self._log),
        )
        graph.add_edge(START, "retrieve")
        graph.add_conditional_edges(
            "retrieve", self._route, {"respond": "respond", "abstain": "abstain"}
        )
        graph.add_edge("respond", END)
        graph.add_edge("abstain", END)
        return graph.compile(checkpointer=MemorySaver())

    async def run(
        self, question: str, auth: AuthContext, *, metadata_filter: MetadataFilter | None = None
    ) -> CopilotAnswer:
        """Answer ``question`` grounded in retrieved sources, or abstain."""
        final = await self._app.ainvoke(
            {"question": question, "auth": auth, "filter": metadata_filter or MetadataFilter()},
            config={"configurable": {"thread_id": uuid4().hex}},
        )
        return cast(CopilotAnswer, final["answer"])
