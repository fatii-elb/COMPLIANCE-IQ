"""Typed, validated tools that bounded agents may call.

A *tool* is a named capability with a Pydantic argument schema and an async
handler that returns text. Typing the arguments blocks malformed calls; the
:class:`ToolRegistry` is the allow-list source from which each agent is granted a
subset. Tool output is untrusted and is injection-scanned by the agent layer
before it is trusted.

- :class:`Tool` / :class:`ToolRegistry` — the registry primitives.
- :class:`AgentBudget` — per-run iteration and wall-clock limits.
- :func:`build_corpus_tools` — the built-in ``search_corpus`` knowledge tool.
"""

from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.corpus_tools import (
    SearchCorpusArgs,
    build_corpus_tools,
)
from complianceiq.application.tools.registry import Tool, ToolHandler, ToolRegistry

__all__ = [
    "AgentBudget",
    "SearchCorpusArgs",
    "Tool",
    "ToolHandler",
    "ToolRegistry",
    "build_corpus_tools",
]
