"""Shared, deliberately conservative analysis of AWS IAM-style policy
documents (S3 bucket policies, KMS key policies, IAM managed policies).

Every check here is a narrow, explainable pattern match — never a full
IAM policy simulator. AWS's own policy evaluation logic accounts for
``NotPrincipal``, ``NotAction``, every ``Condition`` operator, explicit
``Deny`` precedence across multiple policies, SCPs, permission
boundaries, and more; reimplementing that here would be exactly the
kind of speculative complexity this phase is instructed to avoid. These
functions each answer one narrow, literal question and are named for
exactly that question, so a Rule using them can't be misled into
thinking they mean more than they do.

Used by three sub-collectors (S3, KMS, IAM) that would otherwise each
duplicate the same "does this statement grant a wildcard principal /
full admin" logic.
"""

from __future__ import annotations

from typing import Any, Mapping


def _statements(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    statement = document.get("Statement", [])
    if isinstance(statement, Mapping):
        return [statement]
    if isinstance(statement, list):
        return statement
    return []


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def policy_allows_public_principal(document: Mapping[str, Any] | None) -> bool:
    """True if any unconditional ``Allow`` statement grants access to
    principal ``"*"`` (or ``{"AWS": "*"}``).

    A statement carrying any ``Condition`` block is treated as *not*
    public here — conservatively, since judging whether a given
    condition actually narrows exposure (e.g. ``aws:SourceIp`` with a
    wide CIDR) is exactly the kind of policy-simulation this module
    deliberately does not attempt.
    """

    if not document:
        return False
    for statement in _statements(document):
        if statement.get("Effect") != "Allow":
            continue
        if statement.get("Condition"):
            continue
        principal = statement.get("Principal")
        if principal == "*":
            return True
        if isinstance(principal, Mapping) and "*" in _as_list(principal.get("AWS")):
            return True
    return False


def policy_grants_full_admin(document: Mapping[str, Any] | None) -> bool:
    """True if any ``Allow`` statement grants ``Action: "*"`` over
    ``Resource: "*"`` — the literal AWS-managed ``AdministratorAccess``
    shape, not an approximation of "broad" permissions.
    """

    if not document:
        return False
    for statement in _statements(document):
        if statement.get("Effect") != "Allow":
            continue
        if "*" in _as_list(statement.get("Action")) and "*" in _as_list(statement.get("Resource")):
            return True
    return False
