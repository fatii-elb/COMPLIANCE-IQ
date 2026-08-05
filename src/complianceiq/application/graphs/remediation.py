"""Remediation graph — a Finding becomes a (never-applied) Terraform proposal.

Flow: ``START → retrieve → generate → validate → END``.

- **generate** produces a Terraform snippet and a source-grounded justification.
- **validate** statically scans the Terraform for overly-permissive patterns; an
  unsafe "fix" raises :class:`WorkflowError` rather than being offered.

The resulting :class:`RemediationProposal` always has ``approved=False`` (rule 2);
this service proposes, a human disposes.
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
from complianceiq.domain.entities.remediation import RemediationProposal
from complianceiq.domain.exceptions import WorkflowError
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.models import TaskClass
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.policies.grounding import verify_citations
from complianceiq.domain.policies.iac_safety import validate_terraform
from complianceiq.domain.policies.prompt_safety import wrap_untrusted


class RemediationState(TypedDict, total=False):
    finding: Finding
    auth: AuthContext
    context: Any  # AssembledContext
    proposal: RemediationProposal
    trace: Annotated[list[TraceEvent], operator.add]


class RemediationGraph:
    """Builds and runs the remediation-proposal state graph."""

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
        return {"context": context}

    async def _generate(self, state: dict[str, Any]) -> dict[str, Any]:
        finding: Finding = state["finding"]
        auth: AuthContext = state["auth"]
        context = state["context"]

        rendered, _ = self._prompts.render(
            "remediation",
            {"finding": finding_summary(finding), "context": wrap_untrusted(context.text)},
        )
        request = LLMRequest(
            messages=[LLMMessage.system(SYSTEM_GROUNDED), LLMMessage.user(rendered)],
            task=TaskClass.REASONING,
            feature="remediate",
        )
        completion = await self._gateway.generate(request, auth)
        verified = verify_citations(context.citations, context.citations).verified

        terraform = completion.text.strip() or "# no remediation generated"
        control_ids = ", ".join(c.control_id for c in verified) or "the retrieved controls"
        proposal = RemediationProposal(
            finding_id=finding.id,
            terraform=terraform,
            justification=(
                f"Proposed remediation for {finding.control_id}, grounded in {control_ids}. "
                "Requires human review before any change is applied."
            ),
            citations=verified,
            # approved is force-set to False by the model itself (rule 2).
        )
        return {"proposal": proposal}

    async def _validate(self, state: dict[str, Any]) -> dict[str, Any]:
        proposal: RemediationProposal = state["proposal"]
        issues = validate_terraform(proposal.terraform)
        if issues:
            self._log.warning("remediation_unsafe", issues=issues, finding=proposal.finding_id)
            raise WorkflowError(
                "generated remediation failed static safety validation",
                details={"issues": issues},
            )
        return {"_detail": "iac validated"}

    def _build(self) -> Any:
        graph: StateGraph = StateGraph(RemediationState)
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
            "validate",
            traced_node(
                "validate", self._validate, timeout_seconds=self._timeout, logger=self._log
            ),
        )
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", "validate")
        graph.add_edge("validate", END)
        return graph.compile(checkpointer=MemorySaver())

    async def run(self, finding: Finding, auth: AuthContext) -> RemediationProposal:
        """Produce a validated, never-applied remediation proposal for a finding."""
        final = await self._app.ainvoke(
            {"finding": finding, "auth": auth},
            config={"configurable": {"thread_id": uuid4().hex}},
        )
        return cast(RemediationProposal, final["proposal"])
