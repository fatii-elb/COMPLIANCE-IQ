"""The :class:`AuthContext` value object.

The verified identity behind a request. The Core Service issues JWTs; this
service only *verifies* them (Phase 6) and projects the trusted claims into an
:class:`AuthContext`. Every use case receives an ``AuthContext`` and every
data-access call is scoped by its ``tenant_id`` — this object is how tenant
isolation is carried through the application.
"""

from __future__ import annotations

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.identifiers import NonEmptyStr, TenantId


class AuthContext(FrozenModel):
    """The authenticated principal and tenant behind a request.

    Attributes:
        sub: Subject — the authenticated principal (user or service account).
        tenant_id: The tenant the principal is acting within. All access is
            scoped by this value.
        roles: The principal's roles, used for RBAC authorization checks.
    """

    sub: NonEmptyStr
    tenant_id: TenantId
    roles: list[NonEmptyStr] = Field(default_factory=list)

    def has_role(self, role: str) -> bool:
        """Return whether the principal holds ``role``."""
        return role in self.roles
