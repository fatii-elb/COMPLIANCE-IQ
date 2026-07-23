"""Tests for AuthContext RBAC helper and the Page pagination envelope."""

from __future__ import annotations

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.pagination import Page


def test_auth_context_role_membership() -> None:
    ctx = AuthContext(sub="user-1", tenant_id="tenant-a", roles=["analyst", "admin"])
    assert ctx.has_role("admin") is True
    assert ctx.has_role("auditor") is False


def test_page_has_more_when_items_remain() -> None:
    page = Page[str](items=["a", "b"], total=5, limit=2, offset=0)
    assert page.has_more is True


def test_page_has_no_more_on_last_page() -> None:
    page = Page[str](items=["e"], total=5, limit=2, offset=4)
    assert page.has_more is False
