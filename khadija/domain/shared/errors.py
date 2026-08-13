"""Domain exceptions.

Every failure mode the Domain can produce is represented by a specific
subclass of :class:`DomainError`. Nothing in ``domain/`` raises a bare
``Exception`` or ``ValueError`` for a business-rule violation.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every exception raised by the Domain layer."""


class TenantIsolationViolation(DomainError):
    """A cross-tenant access or mutation was attempted.

    Raised whenever an operation would let data belonging to one tenant
    become visible to, or combined with, another tenant's aggregate
    (e.g. inserting a node into a :class:`ResourceGraph` scoped to a
    different tenant).
    """


class InvalidResource(DomainError):
    """A :class:`NormalizedResource` was constructed with invalid data."""


class InvalidResourceRelationship(DomainError):
    """A :class:`ResourceRelationship` was constructed with invalid data."""


class InvalidFinding(DomainError):
    """A :class:`Finding` was constructed with invalid or incomplete data."""


class InvalidRule(DomainError):
    """A :class:`Rule` was constructed with invalid metadata (blank
    framework, control_id, or domain category).
    """


class InvalidRuleCondition(DomainError):
    """A rule condition is malformed, or references an unknown operator or
    unregistered graph function.
    """


class GraphIntegrityViolation(DomainError):
    """A :class:`ResourceGraph` mutation would break referential integrity
    (e.g. an edge referencing a node that does not exist, or a duplicate
    node).
    """


class InvalidAttackPath(DomainError):
    """An :class:`AttackPath` was constructed with invalid or inconsistent
    data (cross-tenant nodes, dangling edges, or a blocked path carrying a
    non-zero risk score).
    """


class InvalidScoreValue(DomainError):
    """A risk-related score (``RiskScore``, ``ConfidenceScore``, or one of
    the weighted factors feeding ``RiskScore.calculate``) is outside its
    valid ``[0, 100]`` bound.
    """


class InvalidDriftEvent(DomainError):
    """A :class:`DriftEvent` was constructed with invalid or inconsistent
    data.
    """


class InvalidComplianceData(DomainError):
    """A ``ComplianceFramework``, ``ControlMapping``, or
    ``ComplianceAssessment`` was constructed with invalid data.
    """


class InvalidScan(DomainError):
    """A ``Scan`` aggregate was constructed or transitioned invalidly
    (Phase 4). Covers both malformed scan data and illegal status
    transitions — the state machine is a domain invariant, so violating
    it is a domain error, not a persistence error.
    """


class InvalidScanTarget(DomainError):
    """A ``ScanTarget`` did not identify a scannable cloud scope
    (Phase 4).
    """


class InvalidFindingLifecycle(DomainError):
    """An illegal transition in the logical finding lifecycle
    (Phase 4) — e.g. reopening a finding that was never resolved.
    """
