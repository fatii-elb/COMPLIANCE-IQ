"""Constrained string types for identifiers.

These annotated aliases give identifiers a distinct *name* in signatures and
schemas while enforcing that they are never empty or whitespace-only. Empty
identifiers are a common source of silent bugs — most dangerously an empty
``tenant_id``, which would defeat tenant isolation — so we reject them at every
boundary rather than trusting callers.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

#: A trimmed, non-empty string. The building block for all identifiers.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

#: Identifies a tenant (client organisation). The single most important field in
#: the system: every query, cache key, log line, and storage write is scoped by
#: it. Enforced non-empty so a missing tenant can never widen a query's scope.
TenantId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]

#: Identifies a cloud resource within a tenant.
ResourceId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]

#: Identifies a control within a framework (e.g. an ISO control reference or a
#: Loi 05-20 article number).
ControlId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
