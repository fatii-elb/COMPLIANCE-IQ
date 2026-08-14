"""HTTP adapter for the Core Service findings API (Phase 6).

Calls the real Core over REST (``GET /api/v1/findings`` and
``/api/v1/findings/{id}``), forwarding the caller's JWT so the Core authorizes
the request against the same identity. Failures are translated into domain
exceptions the presentation layer already knows how to render, and — as
defense-in-depth — every finding the Core returns is re-checked against the
caller's tenant before it is trusted (rule 1), so a Core bug can never leak
another tenant's data through us.

Design mirrors the LLM provider adapters: an injectable ``httpx.AsyncClient`` so
the mapping logic is tested offline with ``httpx.MockTransport`` (no network).
"""

from __future__ import annotations

import httpx

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.pagination import Page
from complianceiq.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DependencyUnavailableError,
    NotFoundError,
)
from complianceiq.domain.policies.tenant_isolation import assert_same_tenant
from complianceiq.domain.ports.core import CoreClient
from complianceiq.domain.value_objects.enums import ComplianceStatus, Framework, Severity

_FINDINGS_PATH = "/api/v1/findings"


class HttpCoreClient(CoreClient):
    """Adapter over the Core Service's REST findings API."""

    def __init__(
        self,
        *,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    @staticmethod
    def _headers(bearer_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"}

    async def _get(self, path: str, *, bearer_token: str, params: dict[str, str]) -> httpx.Response:
        try:
            response = await self._get_client().get(
                path, headers=self._headers(bearer_token), params=params
            )
        except httpx.HTTPError as exc:
            raise DependencyUnavailableError(
                "Core Service is unreachable",
                details={"reason": type(exc).__name__},
            ) from exc
        self._raise_for_status(response)
        return response

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        code = response.status_code
        if code < 400:
            return
        if code == 401:
            raise AuthenticationError("Core Service rejected the token")
        if code == 403:
            raise AuthorizationError("Core Service denied access")
        if code == 404:
            raise NotFoundError("finding not found")
        raise DependencyUnavailableError("Core Service returned an error", details={"status": code})

    async def get_finding(
        self, auth: AuthContext, finding_id: str, *, bearer_token: str
    ) -> Finding:
        response = await self._get(
            f"{_FINDINGS_PATH}/{finding_id}", bearer_token=bearer_token, params={}
        )
        finding = Finding.model_validate(response.json())
        # Defense-in-depth: never trust the Core returned the right tenant.
        assert_same_tenant(
            expected_tenant_id=auth.tenant_id,
            actual_tenant_id=finding.tenant_id,
            resource_kind="finding",
        )
        return finding

    async def list_findings(
        self,
        auth: AuthContext,
        *,
        bearer_token: str,
        framework: Framework | None = None,
        severity: Severity | None = None,
        status: ComplianceStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[Finding]:
        params: dict[str, str] = {"limit": str(limit), "offset": str(offset)}
        if framework is not None:
            params["framework"] = framework.value
        if severity is not None:
            params["severity"] = severity.value
        if status is not None:
            params["status"] = status.value

        response = await self._get(_FINDINGS_PATH, bearer_token=bearer_token, params=params)
        page = Page[Finding].model_validate(response.json())
        for finding in page.items:
            assert_same_tenant(
                expected_tenant_id=auth.tenant_id,
                actual_tenant_id=finding.tenant_id,
                resource_kind="finding",
            )
        return page
