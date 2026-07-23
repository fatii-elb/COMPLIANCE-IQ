"""Shared Pydantic base models for domain types.

Two bases express intent:

- :class:`FrozenModel` — immutable value objects and data-transfer contracts.
  Immutability makes them safe to share across async tasks and cache without
  defensive copying, and prevents accidental mutation of a finding after it has
  been validated at a boundary.
- :class:`DomainModel` — mutable domain entities that legitimately change state
  during a use case.

Both forbid unknown fields (``extra="forbid"``): a payload with a typo or an
unexpected field is a contract violation and must fail loudly at the boundary,
not be silently dropped.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Immutable, strictly-validated base for value objects and contracts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class DomainModel(BaseModel):
    """Mutable, strictly-validated base for stateful domain entities."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )
