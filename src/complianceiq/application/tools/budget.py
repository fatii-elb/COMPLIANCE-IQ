"""Agent budgets — the guardrails that keep agents bounded, not free-roaming.

An agent that can call tools in a loop must have hard limits, or a bug (or an
adversarial input) could make it call tools forever, burning time and money. A
:class:`AgentBudget` caps both the number of tool calls and the wall-clock time an
agent run may consume.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel


class AgentBudget(FrozenModel):
    """Hard limits on a single agent run.

    Attributes:
        max_iterations: Maximum number of tool calls allowed in one run.
        wall_clock_seconds: Maximum elapsed time for the run.
    """

    max_iterations: int = Field(default=8, ge=1, le=100)
    wall_clock_seconds: float = Field(default=60.0, gt=0)
