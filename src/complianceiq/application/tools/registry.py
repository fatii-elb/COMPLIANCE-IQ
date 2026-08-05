"""Tool registry — typed, validated tools agents may call.

A *tool* is a named capability with a **typed argument schema** (a Pydantic
model) and an async handler. Typing the arguments means an agent (or a model)
cannot call a tool with malformed input — arguments are validated before the
handler runs. Tools return **text**, which the bounded-agent layer scans for
prompt injection before trusting it.

This registry is the allow-list source: an agent is granted a *subset* of the
registered tools, and can call nothing else (see :mod:`complianceiq.application.agents.base`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import ValidationError as DomainValidationError
from complianceiq.domain.exceptions import WorkflowError

#: A tool handler takes validated args + the auth context and returns text.
ToolHandler = Callable[[BaseModel, AuthContext], Awaitable[str]]


@dataclass(frozen=True)
class Tool:
    """A single typed tool.

    Attributes:
        name: Unique tool name (used in allow-lists).
        description: What the tool does (shown to models in later phases).
        args_model: Pydantic model validating the tool's arguments.
        handler: Async function ``(validated_args, auth) -> str``.
    """

    name: str
    description: str
    args_model: type[BaseModel]
    handler: ToolHandler

    async def invoke(self, raw_args: dict[str, object], auth: AuthContext) -> str:
        """Validate ``raw_args`` against the schema and run the handler."""
        try:
            args = self.args_model.model_validate(raw_args)
        except ValidationError as exc:
            raise DomainValidationError(
                f"invalid arguments for tool '{self.name}'",
                details={"tool": self.name, "errors": exc.errors()},
            ) from exc
        return await self.handler(args, auth)


class ToolRegistry:
    """A registry of tools, addressed by name."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        """Register a tool (names must be unique)."""
        if tool.name in self._tools:
            raise WorkflowError(f"tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Return a tool by name, or raise if unknown."""
        if name not in self._tools:
            raise WorkflowError(f"unknown tool '{name}'", details={"tool": name})
        return self._tools[name]

    def names(self) -> list[str]:
        """Return all registered tool names (sorted)."""
        return sorted(self._tools)
