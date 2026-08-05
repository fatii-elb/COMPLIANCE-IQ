"""Shared builders for the Phase 4 workflow/agent tests.

Everything here is deterministic and offline: a duck-typed fake gateway with a
scriptable reply, a retriever with the sample corpus ingested (stub embedder),
and the real prompt registry loaded from the ``prompts/`` assets. Using a
lightweight fake gateway (instead of the full routing/provider stack) keeps these
tests focused on the graph/agent logic under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from complianceiq.application.knowledge.config import RetrievalConfig
from complianceiq.application.knowledge.context_assembly import ContextAssembler
from complianceiq.application.knowledge.retrieval import HybridRetriever
from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.llm.requests import LLMRequest
from complianceiq.domain.llm.responses import Completion, FinishReason, TokenUsage
from complianceiq.domain.value_objects.enums import (
    ComplianceStatus,
    Framework,
    RiskDomain,
    Severity,
)
from complianceiq.infrastructure.prompts.loader import load_prompts
from tests.unit.knowledge.conftest import build_ingested_retriever

AUTH = AuthContext(sub="analyst-1", tenant_id="tenant-a")

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class FakeGateway:
    """A duck-typed stand-in for :class:`AIGateway` with a scripted reply.

    Records every request so tests can assert on what the graph/agent asked the
    model, and returns a fixed text (configurable) as the completion.
    """

    def __init__(self, reply: str = "Grounded explanation citing [1].") -> None:
        self.reply = reply
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest, auth: AuthContext) -> Completion:
        self.requests.append(request)
        return Completion(
            text=self.reply,
            provider=ProviderName.FAKE,
            model_id="fake-model",
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            finish_reason=FinishReason.STOP,
        )


def load_prompt_registry() -> PromptRegistry:
    """Load the real prompt registry from the repository's ``prompts/`` assets."""
    return PromptRegistry(load_prompts(PROMPTS_DIR))


async def build_retrieval_stack(
    *, config: RetrievalConfig | None = None
) -> tuple[HybridRetriever, ContextAssembler, RetrievalConfig]:
    """Build an ingested retriever + assembler + config for graph/agent tests."""
    config = config or RetrievalConfig()
    retriever, _, _ = await build_ingested_retriever(config=config)
    return retriever, ContextAssembler(), config


def make_finding(
    *,
    control_id: str = "PR.AA-01",
    framework: Framework = Framework.NIST_CSF,
    domain: RiskDomain = RiskDomain.IAM,
    severity: Severity = Severity.HIGH,
    resource_id: str = "arn:aws:iam::acct:user/svc",
) -> Finding:
    """Build a deterministic :class:`Finding` for tests."""
    return Finding(
        id="finding-1",
        tenant_id="tenant-a",
        resource_id=resource_id,
        rule_id="rule-iam-key-rotation",
        framework=framework,
        control_id=control_id,
        domain=domain,
        status=ComplianceStatus.FAIL,
        severity=severity,
        evidence={"expected": "rotation<=90d", "actual": "never"},
        detected_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
