"""Prompt registry — look up and render versioned prompts by id.

The registry holds the loaded :class:`PromptTemplate` assets and serves the
latest version of each by default (or a pinned version). Rendering delegates to
the template (which validates variables). Recording ``prompt.key`` (``id@version``)
in traces makes every generation attributable to an exact prompt version.
"""

from __future__ import annotations

from collections.abc import Iterable

from complianceiq.domain.exceptions import PromptError
from complianceiq.domain.prompts.template import PromptTemplate


class PromptRegistry:
    """An in-memory index of prompt templates keyed by id (and version)."""

    def __init__(self, templates: Iterable[PromptTemplate]) -> None:
        self._by_key: dict[str, PromptTemplate] = {}
        self._latest: dict[str, PromptTemplate] = {}
        for template in templates:
            self._by_key[template.key] = template
            current = self._latest.get(template.id)
            if current is None or template.version > current.version:
                self._latest[template.id] = template

    def get(self, prompt_id: str, *, version: int | None = None) -> PromptTemplate:
        """Return a prompt by id (latest by default, or a pinned ``version``)."""
        if version is not None:
            key = f"{prompt_id}@{version}"
            if key not in self._by_key:
                raise PromptError(f"unknown prompt '{key}'", details={"prompt": key})
            return self._by_key[key]
        if prompt_id not in self._latest:
            raise PromptError(f"unknown prompt '{prompt_id}'", details={"prompt": prompt_id})
        return self._latest[prompt_id]

    def render(
        self, prompt_id: str, variables: dict[str, str], *, version: int | None = None
    ) -> tuple[str, str]:
        """Render a prompt; return ``(rendered_text, prompt_key)``.

        The returned ``prompt_key`` (``id@version``) is recorded in traces so the
        output is attributable to an exact prompt version.
        """
        template = self.get(prompt_id, version=version)
        return template.render(variables), template.key

    def ids(self) -> list[str]:
        """Return the ids of all registered prompts (sorted)."""
        return sorted(self._latest)
