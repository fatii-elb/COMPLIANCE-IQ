"""Read-only findings endpoints (surfacing the Core Service).

These expose the *existing* :class:`CoreClient` capability over HTTP so the
frontend can list and open findings without the client having to POST finding
bodies. They add no new business logic: every call is delegated to the wired
Core client, tenant-scoped by the caller's :class:`AuthContext`, forwarding the
caller's bearer token (end-to-end identity — non-negotiable rule 1).

- ``GET /api/v1/findings``       — the caller's tenant findings (filter + page).
- ``GET /api/v1/findings/{id}``  — a single finding by id (404 if not in tenant).

Offline (``core_client == "stub"``) these read the seeded in-process dataset;
against a live Core (``core_client == "http"``) they read the real service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.pagination import Page
from complianceiq.domain.ports.core import CoreClient
from complianceiq.domain.value_objects.enums import ComplianceStatus, Framework, Severity
from complianceiq.presentation.container import (
    get_auth_context,
    get_bearer_token,
    get_core_client,
)

router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


@router.get("", response_model=Page[Finding], summary="List the caller's findings")
async def list_findings(
    auth: AuthContext = Depends(get_auth_context),
    token: str = Depends(get_bearer_token),
    core: CoreClient = Depends(get_core_client),
    framework: Framework | None = Query(default=None, description="Filter by framework."),
    severity: Severity | None = Query(default=None, description="Filter by severity."),
    status: ComplianceStatus | None = Query(default=None, description="Filter by pass/fail."),
    limit: int = Query(default=100, ge=1, le=500, description="Max items to return."),
    offset: int = Query(default=0, ge=0, description="Items to skip (paging)."),
) -> Page[Finding]:
    """Return a page of the caller's tenant findings, with optional filters."""
    return await core.list_findings(
        auth,
        bearer_token=token,
        framework=framework,
        severity=severity,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/{finding_id}", response_model=Finding, summary="Get one finding by id")
async def get_finding(
    finding_id: str,
    auth: AuthContext = Depends(get_auth_context),
    token: str = Depends(get_bearer_token),
    core: CoreClient = Depends(get_core_client),
) -> Finding:
    """Return a single finding, scoped to the caller's tenant (404 if absent)."""
    return await core.get_finding(auth, finding_id, bearer_token=token)
