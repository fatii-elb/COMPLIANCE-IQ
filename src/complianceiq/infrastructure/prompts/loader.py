"""Prompt loader — read ``.prompt`` asset files into domain templates.

A ``.prompt`` file has a small frontmatter block (``key: value`` lines) followed
by a ``---`` separator and the body:

    id: enrich_finding
    version: 1
    description: Explain why a finding is non-compliant, grounded in context.
    variables: finding, context
    ---
    <the prompt body, using {{ finding }} and {{ context }} placeholders>

Keeping prompts in files (not code) makes them reviewable, diff-able, and
versioned as assets. Parsing is dependency-free (no YAML) so the loader stays
light.
"""

from __future__ import annotations

from pathlib import Path

from complianceiq.domain.exceptions import PromptError
from complianceiq.domain.prompts.template import PromptTemplate

_SEPARATOR = "---"


def parse_prompt(text: str) -> PromptTemplate:
    """Parse a single ``.prompt`` file's contents into a :class:`PromptTemplate`."""
    if _SEPARATOR not in text:
        raise PromptError("prompt file missing '---' frontmatter separator")

    frontmatter, _, body = text.partition(f"\n{_SEPARATOR}")
    meta: dict[str, str] = {}
    for line in frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise PromptError(f"invalid frontmatter line: {line!r}")
        meta[key.strip()] = value.strip()

    if "id" not in meta or "version" not in meta:
        raise PromptError("prompt frontmatter must include 'id' and 'version'")

    variables = [v.strip() for v in meta.get("variables", "").split(",") if v.strip()]
    return PromptTemplate(
        id=meta["id"],
        version=int(meta["version"]),
        description=meta.get("description", ""),
        variables=variables,
        template=body.strip("\n"),
    )


def load_prompts(directory: Path) -> list[PromptTemplate]:
    """Load every ``*.prompt`` file under ``directory`` (sorted, deterministic)."""
    if not directory.exists():
        return []
    return [
        parse_prompt(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.prompt"))
    ]
