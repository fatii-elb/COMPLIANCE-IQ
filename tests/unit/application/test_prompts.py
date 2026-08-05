"""Tests for the prompt subsystem: template rendering, loader, and registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from complianceiq.application.prompts.registry import PromptRegistry
from complianceiq.domain.exceptions import PromptError
from complianceiq.domain.prompts.template import PromptTemplate
from complianceiq.infrastructure.prompts.loader import load_prompts, parse_prompt

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def test_template_renders_declared_variables() -> None:
    tpl = PromptTemplate(id="t", version=1, variables=["name"], template="Hello {{ name }}!")
    assert tpl.render({"name": "world"}) == "Hello world!"
    assert tpl.key == "t@1"


def test_template_leaves_single_braces_untouched() -> None:
    tpl = PromptTemplate(id="t", version=1, variables=["x"], template='{"json": true} and {{ x }}')
    assert tpl.render({"x": "1"}) == '{"json": true} and 1'


def test_template_missing_variable_raises() -> None:
    tpl = PromptTemplate(id="t", version=1, variables=["name"], template="{{ name }}")
    with pytest.raises(PromptError, match="missing variables"):
        tpl.render({})


def test_template_undeclared_placeholder_raises() -> None:
    tpl = PromptTemplate(id="t", version=1, variables=[], template="{{ ghost }}")
    with pytest.raises(PromptError, match="undeclared placeholder"):
        tpl.render({})


def test_parse_prompt_reads_frontmatter_and_body() -> None:
    text = (
        "id: demo\nversion: 2\ndescription: A demo.\nvariables: a, b\n"
        "---\nBody with {{ a }} and {{ b }}.\n"
    )
    tpl = parse_prompt(text)
    assert tpl.id == "demo"
    assert tpl.version == 2
    assert tpl.variables == ["a", "b"]
    assert "Body with" in tpl.template


def test_parse_prompt_requires_separator() -> None:
    with pytest.raises(PromptError, match="separator"):
        parse_prompt("id: x\nversion: 1\nno separator here")


def test_parse_prompt_ignores_comments_and_blank_lines() -> None:
    text = "# a comment\n\nid: demo\nversion: 1\n---\nBody\n"
    assert parse_prompt(text).id == "demo"


def test_parse_prompt_rejects_malformed_frontmatter_line() -> None:
    with pytest.raises(PromptError, match="invalid frontmatter line"):
        parse_prompt("id demo\nversion: 1\n---\nBody")


def test_parse_prompt_requires_id_and_version() -> None:
    with pytest.raises(PromptError, match="must include 'id' and 'version'"):
        parse_prompt("description: no id\n---\nBody")


def test_load_prompts_missing_directory_returns_empty() -> None:
    assert load_prompts(Path("/nonexistent/prompts/dir")) == []


def test_registry_serves_latest_version() -> None:
    v1 = PromptTemplate(id="p", version=1, template="v1")
    v2 = PromptTemplate(id="p", version=2, template="v2")
    registry = PromptRegistry([v1, v2])
    assert registry.get("p").version == 2
    assert registry.get("p", version=1).version == 1


def test_registry_unknown_prompt_raises() -> None:
    registry = PromptRegistry([])
    with pytest.raises(PromptError, match="unknown prompt"):
        registry.get("nope")


def test_bundled_prompts_load_and_declare_their_variables() -> None:
    templates = load_prompts(_PROMPTS_DIR)
    ids = {t.id for t in templates}
    assert {
        "enrich_finding",
        "copilot_answer",
        "remediation",
        "report_summary",
        "risk_narrative",
    } <= ids
    # Every bundled prompt renders with its declared variables supplied.
    for tpl in templates:
        rendered = tpl.render({name: f"<{name}>" for name in tpl.variables})
        assert rendered
