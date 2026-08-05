"""Prompt templates as versioned, validated assets.

Prompts are not string literals scattered through the code — they are *assets*
with an id, a version, declared variables, and a changelog, loaded from files.
Treating them this way lets us version, review, A/B-test, and roll back prompts,
and record which prompt version produced any given output (for evaluation and
audit).

Rendering is a pure domain operation: it validates that every declared variable
is supplied and that no placeholder is left unfilled, so a malformed prompt fails
loudly at render time rather than silently sending ``{{ context }}`` to a model.

Placeholders use ``{{ name }}`` (double braces) deliberately: prompt bodies often
contain JSON/code with single braces, which must pass through untouched.
"""

from __future__ import annotations

import re

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.exceptions import PromptError
from complianceiq.domain.value_objects.identifiers import NonEmptyStr

_PLACEHOLDER = re.compile(r"{{\s*(\w+)\s*}}")


class PromptTemplate(FrozenModel):
    """A single versioned prompt.

    Attributes:
        id: Stable prompt identifier (e.g. ``enrich_finding``).
        version: Monotonic version number; higher is newer.
        description: What the prompt does / changelog note.
        variables: The names the template expects to be filled.
        template: The prompt body, using ``{{ variable }}`` placeholders.
    """

    id: NonEmptyStr
    version: int = Field(ge=1)
    description: str = ""
    variables: list[str] = Field(default_factory=list)
    template: NonEmptyStr

    @property
    def key(self) -> str:
        """A unique ``id@version`` key, recorded in traces/eval runs."""
        return f"{self.id}@{self.version}"

    def render(self, variables: dict[str, str]) -> str:
        """Render the template with ``variables``.

        Args:
            variables: Values for every declared variable.

        Returns:
            The rendered prompt string.

        Raises:
            PromptError: If a declared variable is missing, or the template
                references a placeholder not provided.
        """
        missing = [name for name in self.variables if name not in variables]
        if missing:
            raise PromptError(
                f"prompt '{self.key}' missing variables: {sorted(missing)}",
                details={"prompt": self.key, "missing": sorted(missing)},
            )

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in variables:
                raise PromptError(
                    f"prompt '{self.key}' references undeclared placeholder '{name}'",
                    details={"prompt": self.key, "placeholder": name},
                )
            return str(variables[name])

        return _PLACEHOLDER.sub(_replace, self.template)
