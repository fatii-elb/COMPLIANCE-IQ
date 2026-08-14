"""Bounded agents — the guardrails around tool-using AI.

An *agent* orchestrates a task, optionally calling :mod:`tools <complianceiq.application.tools>`
along the way. Unbounded, that is dangerous: a bug or an adversarial input could
make it loop forever, call tools it should not, or trust poisoned tool output. A
:class:`BoundedAgent` makes every one of those failure modes impossible by
construction, through a :class:`ToolSession` that enforces, on every call:

1. **Allow-list** — an agent may only call the tools explicitly granted to it.
2. **Iteration budget** — a hard cap on the number of tool calls per run.
3. **Wall-clock budget** — a hard cap on elapsed time per run.
4. **Loop detection** — the same tool called with the same arguments twice is
   treated as a non-terminating loop and stopped.
5. **Output scanning** — every tool's output is scanned for prompt injection
   before the agent is allowed to trust it (defence-in-depth, rule 4).

Concrete agents (see this package) subclass :class:`BoundedAgent`; each run opens
one :class:`ToolSession`, so budgets are per-run and never leak between requests.
"""

from __future__ import annotations

import json

from complianceiq.application.gateway.ai_gateway import GatewayLogger
from complianceiq.application.graphs._common import NullGraphLogger
from complianceiq.application.tools.budget import AgentBudget
from complianceiq.application.tools.registry import ToolRegistry
from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import UnsafeContentError, WorkflowError
from complianceiq.domain.policies.prompt_safety import scan_for_injection
from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.value_objects.enums import Severity


class ToolSession:
    """A single agent run's bounded access to tools.

    One session is opened per :meth:`BoundedAgent.session` and enforces the
    agent's budget across all tool calls within that run. State (iteration count,
    start time, seen-call signatures) lives on the session, so budgets are
    per-run and never shared between concurrent requests.
    """

    def __init__(
        self,
        *,
        agent_name: str,
        registry: ToolRegistry,
        allowed_tools: frozenset[str],
        budget: AgentBudget,
        clock: Clock,
        injection_threshold: Severity,
        logger: GatewayLogger,
    ) -> None:
        self._agent = agent_name
        self._registry = registry
        self._allowed = allowed_tools
        self._budget = budget
        self._clock = clock
        self._threshold = injection_threshold
        self._log = logger
        self._iterations = 0
        self._started = clock.now()
        self._seen: set[str] = set()

    @property
    def iterations(self) -> int:
        """How many tool calls this session has made so far."""
        return self._iterations

    async def call(self, name: str, args: dict[str, object], auth: AuthContext) -> str:
        """Invoke tool ``name`` under the session's budget and safety controls.

        Raises:
            WorkflowError: The tool is not allow-listed, or the iteration /
                wall-clock budget is exhausted, or a loop was detected.
            UnsafeContentError: The tool's output tripped the injection scanner.
            ValidationError: The arguments failed the tool's schema.
        """
        if name not in self._allowed:
            raise WorkflowError(
                f"agent '{self._agent}' may not call tool '{name}'",
                details={"agent": self._agent, "tool": name, "allowed": sorted(self._allowed)},
            )

        elapsed = (self._clock.now() - self._started).total_seconds()
        if elapsed >= self._budget.wall_clock_seconds:
            raise WorkflowError(
                f"agent '{self._agent}' exceeded its wall-clock budget",
                details={"agent": self._agent, "elapsed_s": round(elapsed, 3)},
            )

        if self._iterations >= self._budget.max_iterations:
            raise WorkflowError(
                f"agent '{self._agent}' exceeded its iteration budget",
                details={"agent": self._agent, "max_iterations": self._budget.max_iterations},
            )

        signature = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
        if signature in self._seen:
            raise WorkflowError(
                f"agent '{self._agent}' repeated an identical tool call (loop detected)",
                details={"agent": self._agent, "tool": name},
            )
        self._seen.add(signature)
        self._iterations += 1

        tool = self._registry.get(name)
        output = await tool.invoke(args, auth)

        scan = scan_for_injection(output)
        if scan.exceeds(self._threshold):
            self._log.warning(
                "agent_tool_output_unsafe",
                agent=self._agent,
                tool=name,
                signals=[s.label for s in scan.signals],
            )
            raise UnsafeContentError(
                f"tool '{name}' returned content that tripped the injection scanner",
                details={"tool": name, "labels": [s.label for s in scan.signals]},
            )
        return output


class BoundedAgent:
    """Base class for tool-using agents with hard, enforced limits.

    Subclasses declare which tools they are allowed to use and implement their
    task logic, opening a :class:`ToolSession` (via :meth:`session`) for any run
    that touches tools. The base class owns nothing task-specific — only the
    guardrails.
    """

    def __init__(
        self,
        *,
        name: str,
        registry: ToolRegistry,
        allowed_tools: frozenset[str] | set[str] | None = None,
        budget: AgentBudget | None = None,
        clock: Clock,
        injection_threshold: Severity = Severity.HIGH,
        logger: GatewayLogger | None = None,
    ) -> None:
        self.name = name
        self._registry = registry
        self._allowed = frozenset(allowed_tools or ())
        self._budget = budget or AgentBudget()
        self._clock = clock
        self._threshold = injection_threshold
        self._log: GatewayLogger = logger or NullGraphLogger()
        # Fail fast: an agent may only be granted tools that actually exist.
        registered = set(registry.names())
        unknown = self._allowed - registered
        if unknown:
            raise WorkflowError(
                f"agent '{name}' granted unknown tools: {sorted(unknown)}",
                details={"agent": name, "unknown": sorted(unknown)},
            )

    def session(self) -> ToolSession:
        """Open a fresh, budget-bounded tool session for one agent run."""
        return ToolSession(
            agent_name=self.name,
            registry=self._registry,
            allowed_tools=self._allowed,
            budget=self._budget,
            clock=self._clock,
            injection_threshold=self._threshold,
            logger=self._log,
        )
