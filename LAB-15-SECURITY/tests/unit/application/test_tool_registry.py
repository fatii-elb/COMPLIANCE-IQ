"""Tests for the tool registry and typed argument validation."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from complianceiq.application.tools.registry import Tool, ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import ValidationError as DomainValidationError
from complianceiq.domain.exceptions import WorkflowError

AUTH = AuthContext(sub="u", tenant_id="tenant-a")


class _Args(BaseModel):
    n: int = Field(ge=0)


def _tool() -> Tool:
    async def _handler(args: BaseModel, auth: AuthContext) -> str:
        assert isinstance(args, _Args)
        return f"n={args.n}"

    return Tool(name="echo", description="echo n", args_model=_Args, handler=_handler)


async def test_tool_validates_and_invokes() -> None:
    assert await _tool().invoke({"n": 3}, AUTH) == "n=3"


async def test_tool_rejects_invalid_arguments() -> None:
    with pytest.raises(DomainValidationError):
        await _tool().invoke({"n": -1}, AUTH)


def test_registry_rejects_duplicate_names() -> None:
    registry = ToolRegistry([_tool()])
    with pytest.raises(WorkflowError, match="already registered"):
        registry.register(_tool())


def test_registry_unknown_tool_raises() -> None:
    with pytest.raises(WorkflowError, match="unknown tool"):
        ToolRegistry().get("nope")


def test_registry_lists_names_sorted() -> None:
    async def _h(args: BaseModel, auth: AuthContext) -> str:
        return "ok"

    b = Tool(name="beta", description="", args_model=_Args, handler=_h)
    a = Tool(name="alpha", description="", args_model=_Args, handler=_h)
    assert ToolRegistry([b, a]).names() == ["alpha", "beta"]
