"""Tests for the domain LLM value objects."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from complianceiq.domain.llm.messages import LLMMessage, MessageRole
from complianceiq.domain.llm.models import ModelCost, ProviderName
from complianceiq.domain.llm.requests import GenerationParams, LLMRequest, ProviderRequest
from complianceiq.domain.llm.responses import Completion, FinishReason, TokenUsage


def test_message_role_trust() -> None:
    assert MessageRole.SYSTEM.is_trusted is True
    assert MessageRole.USER.is_trusted is False
    assert LLMMessage.system("x").role is MessageRole.SYSTEM
    assert LLMMessage.user("x").role is MessageRole.USER


def test_token_usage_total_and_add() -> None:
    a = TokenUsage(input_tokens=3, output_tokens=4)
    b = TokenUsage(input_tokens=1, output_tokens=2)
    assert a.total_tokens == 7
    combined = a + b
    assert combined.input_tokens == 4
    assert combined.output_tokens == 6


def test_model_cost_computation() -> None:
    cost = ModelCost(input_per_million=Decimal("3.00"), output_per_million=Decimal("15.00"))
    # 1,000,000 input tokens = $3.00, 1,000,000 output = $15.00
    assert cost.cost_for(input_tokens=1_000_000, output_tokens=0) == Decimal("3.00")
    assert cost.cost_for(input_tokens=0, output_tokens=2_000_000) == Decimal("30.00")


def test_generation_params_defaults_are_deterministic() -> None:
    params = GenerationParams()
    assert params.temperature == 0.0
    assert params.max_output_tokens == 1024


def test_llm_request_requires_at_least_one_message() -> None:
    with pytest.raises(PydanticValidationError):
        LLMRequest(messages=[])


def test_provider_request_requires_model_and_messages() -> None:
    req = ProviderRequest(model_id="m", messages=[LLMMessage.user("hi")])
    assert req.model_id == "m"
    with pytest.raises(PydanticValidationError):
        ProviderRequest(model_id="", messages=[LLMMessage.user("hi")])


def test_completion_defaults() -> None:
    completion = Completion(
        text="answer",
        provider=ProviderName.FAKE,
        model_id="fake",
        usage=TokenUsage(input_tokens=1, output_tokens=1),
    )
    assert completion.finish_reason is FinishReason.STOP
    assert completion.cached is False
