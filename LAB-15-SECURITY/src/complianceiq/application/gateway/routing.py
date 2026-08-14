"""Model routing table.

Maps each :class:`TaskClass` to an **ordered** list of :class:`ModelSpec`: the
first is the primary model, the rest are the fallback chain tried in order when
the primary provider fails. Routing is *data* — swapping which model serves
"reasoning", or adding a fallback, is a configuration change the gateway reads,
not a code change.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.llm.models import ModelSpec, TaskClass


class RoutingTable(FrozenModel):
    """Task → ordered model candidates, plus the embedding model.

    Attributes:
        routes: For each task, the primary model followed by fallbacks.
        default_task: The task whose route is used when a requested task has no
            explicit entry.
        embedding_model: The model used for embeddings (a distinct concern from
            chat routing).
    """

    routes: dict[TaskClass, list[ModelSpec]] = Field(default_factory=dict)
    default_task: TaskClass = TaskClass.GENERAL
    embedding_model: ModelSpec | None = None

    def plan_for(self, task: TaskClass) -> list[ModelSpec]:
        """Return the ordered candidate models for ``task``.

        Falls back to the ``default_task`` route when the task has no explicit
        entry, so a new task class degrades gracefully instead of failing.
        """
        if self.routes.get(task):
            return self.routes[task]
        return self.routes.get(self.default_task, [])
