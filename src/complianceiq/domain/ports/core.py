"""The :class:`CoreClient` port — reading findings from the Core Service.

The Core Service owns cloud scanning, the rule engine, tenancy, and the
findings/scores API. This AI service *consumes* those findings over REST; it
never scans clouds or writes the Core's tables. This port is how the application
fetches findings without knowing whether they come from a live HTTP service or an
in-process stub.

Every call is **tenant-scoped**: the returned data must belong to the caller's
tenant (``auth.tenant_id``). The ``bearer_token`` is the caller's own JWT,
forwarded to the Core so it authorizes the request against the same identity —
end-to-end tenant propagation, no ambient service credential.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from complianceiq.domain.entities.auth import AuthContext
from complianceiq.domain.entities.finding import Finding
from complianceiq.domain.entities.pagination import Page
from complianceiq.domain.value_objects.enums import ComplianceStatus, Framework, Severity


class CoreClient(ABC):
    """Reads tenant findings from the Core Service (or a stub)."""

    @abstractmethod
    async def get_finding(
        self, auth: AuthContext, finding_id: str, *, bearer_token: str
    ) -> Finding:
        """Fetch a single finding by id, scoped to the caller's tenant.

        Raises:
            NotFoundError: The finding does not exist for this tenant.
            DependencyUnavailableError: The Core Service could not be reached.
        """
        raise NotImplementedError

    @abstractmethod
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
        """List the caller's tenant findings, with optional filters + paging.

        Raises:
            DependencyUnavailableError: The Core Service could not be reached.
        """
        raise NotImplementedError
