"""Tests for tenant-scoped, content-addressed cache keys."""

from __future__ import annotations

from complianceiq.application.gateway.keys import build_cache_key
from complianceiq.domain.llm.messages import LLMMessage
from complianceiq.domain.llm.requests import LLMRequest


def _req(content: str) -> LLMRequest:
    return LLMRequest(messages=[LLMMessage.user(content)])


def test_identical_requests_same_key() -> None:
    assert build_cache_key("t1", _req("hello")) == build_cache_key("t1", _req("hello"))


def test_different_content_different_key() -> None:
    assert build_cache_key("t1", _req("hello")) != build_cache_key("t1", _req("world"))


def test_different_tenant_different_key() -> None:
    # The same content for two tenants must never collide (rule 1).
    assert build_cache_key("t1", _req("hello")) != build_cache_key("t2", _req("hello"))


def test_key_is_tenant_prefixed() -> None:
    assert build_cache_key("tenant-a", _req("hi")).startswith("ai:completion:tenant-a:")
