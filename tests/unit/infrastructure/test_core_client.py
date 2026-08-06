"""Tests for the Core Service clients (stub + HTTP adapter, both offline)."""

from __future__ import annotations

import httpx
import pytest

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.exceptions import (
    AuthenticationError,
    DependencyUnavailableError,
    NotFoundError,
    TenantIsolationError,
)
from complianceiq.domain.value_objects.enums import Severity
from complianceiq.infrastructure.core.http_client import HttpCoreClient
from complianceiq.infrastructure.core.stub_client import StubCoreClient, sample_findings

AUTH_A = AuthContext(sub="u", tenant_id="tenant-a")
AUTH_B = AuthContext(sub="u", tenant_id="tenant-b")


# --------------------------------- stub ------------------------------------ #


async def test_stub_get_finding_returns_tenant_finding() -> None:
    client = StubCoreClient()
    finding = await client.get_finding(AUTH_A, "finding-iam-1", bearer_token="t")
    assert finding.id == "finding-iam-1"
    assert finding.tenant_id == "tenant-a"


async def test_stub_get_finding_unknown_is_not_found() -> None:
    client = StubCoreClient()
    with pytest.raises(NotFoundError):
        await client.get_finding(AUTH_A, "does-not-exist", bearer_token="t")


async def test_stub_get_finding_cross_tenant_is_not_found() -> None:
    # tenant-b asking for tenant-a's finding sees "not found", never the data.
    client = StubCoreClient()
    with pytest.raises(NotFoundError):
        await client.get_finding(AUTH_B, "finding-iam-1", bearer_token="t")


async def test_stub_list_findings_filters_and_pages() -> None:
    client = StubCoreClient()
    page = await client.list_findings(AUTH_A, bearer_token="t", severity=Severity.CRITICAL)
    assert page.total == 1
    assert page.items[0].severity is Severity.CRITICAL

    paged = await client.list_findings(AUTH_A, bearer_token="t", limit=1, offset=0)
    assert len(paged.items) == 1
    assert paged.total == 2
    assert paged.has_more is True


async def test_stub_list_findings_empty_for_unknown_tenant() -> None:
    client = StubCoreClient()
    page = await client.list_findings(AUTH_B, bearer_token="t")
    assert page.total == 0
    assert page.items == []


# ------------------------------- http adapter ------------------------------ #


def _finding_json(tenant_id: str = "tenant-a", finding_id: str = "finding-iam-1") -> dict:
    return sample_findings(tenant_id)[0].model_dump(mode="json") | {"id": finding_id}


def _client_with(handler) -> HttpCoreClient:
    transport = httpx.MockTransport(handler)
    return HttpCoreClient(
        base_url="http://core-stub:9000",
        client=httpx.AsyncClient(transport=transport, base_url="http://core-stub:9000"),
    )


async def test_http_get_finding_parses_and_forwards_token() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization", "")
        return httpx.Response(200, json=_finding_json())

    client = _client_with(handler)
    finding = await client.get_finding(AUTH_A, "finding-iam-1", bearer_token="tok-123")
    assert finding.tenant_id == "tenant-a"
    assert seen["auth"] == "Bearer tok-123"


async def test_http_get_finding_rejects_cross_tenant_payload() -> None:
    # The Core (buggy or malicious) returns another tenant's finding → we block it.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_finding_json(tenant_id="tenant-evil"))

    client = _client_with(handler)
    with pytest.raises(TenantIsolationError):
        await client.get_finding(AUTH_A, "finding-iam-1", bearer_token="t")


async def test_http_list_findings_parses_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"items": [_finding_json()], "total": 1, "limit": 50, "offset": 0},
        )

    client = _client_with(handler)
    page = await client.list_findings(AUTH_A, bearer_token="t")
    assert page.total == 1
    assert page.items[0].tenant_id == "tenant-a"


async def test_http_404_maps_to_not_found() -> None:
    client = _client_with(lambda req: httpx.Response(404, json={}))
    with pytest.raises(NotFoundError):
        await client.get_finding(AUTH_A, "x", bearer_token="t")


async def test_http_401_maps_to_authentication_error() -> None:
    client = _client_with(lambda req: httpx.Response(401, json={}))
    with pytest.raises(AuthenticationError):
        await client.get_finding(AUTH_A, "x", bearer_token="t")


async def test_http_500_maps_to_dependency_unavailable() -> None:
    client = _client_with(lambda req: httpx.Response(503, json={}))
    with pytest.raises(DependencyUnavailableError):
        await client.get_finding(AUTH_A, "x", bearer_token="t")


async def test_http_network_error_maps_to_dependency_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client_with(handler)
    with pytest.raises(DependencyUnavailableError):
        await client.get_finding(AUTH_A, "x", bearer_token="t")
