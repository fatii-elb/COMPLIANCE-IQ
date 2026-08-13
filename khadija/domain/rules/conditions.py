"""Deterministic, pure-Python rule condition evaluator (blueprint §9,
extended per the Phase 3B CSPM conformance design proposal, Part A/B/C).

No dynamic code execution of any kind (no calls to the Python builtins
that execute arbitrary source text) — every condition is a plain nested
``dict`` interpreted by the recursive evaluator below, using three-valued
(Kleene) logic:

* ``MATCHED`` — the condition holds.
* ``NOT_MATCHED`` — the condition does not hold.
* ``INDETERMINATE`` — the data needed to decide was not collected. This
  must never silently become ``MATCHED``/``NOT_MATCHED`` — that is how
  "no hidden compliance" is enforced at the rule layer itself.

Condition shape — five node types, all backward compatible with the
original four (``and``/``or``/``not``/leaf); ``relationship`` is new:

* ``{"and": [condition, ...]}`` / ``{"or": [condition, ...]}`` — at least
  one operand required. Unchanged since Phase 1.
* ``{"not": condition}`` — unchanged since Phase 1.
* ``{"field": "a.b.c", "operator": "equals", "value": ..., "source": "attributes"}``
  — a leaf. ``source`` defaults to ``"attributes"``; ``"tags"`` is also
  supported. ``field`` supports dot-notation for nested lookups.
  Quantifier operators (``any``/``all``/``none``) additionally take a
  ``where`` sub-condition instead of ``value`` — see
  :func:`_evaluate_quantifier`.
* ``{"source": "graph", "function": "<name>", ...}`` — a contextual leaf
  evaluated against an extensible function registry. Unchanged since
  Phase 1: the registry is intentionally empty (no real rule has ever
  needed it) — this is distinct from, and simpler than, the new
  ``relationship`` node below, which is the mechanism real cross-resource
  rules actually use.
* ``{"relationship": "<RelationshipType value>", "direction": "outgoing"|"incoming",
   "target_type"?: str, "where": condition}`` — NEW. Evaluates ``where``
  against every graph neighbor connected via that relationship/direction
  (optionally filtered to ``target_type``), existence-quantified (OR)
  across neighbors. Requires ``graph`` and ``resources_by_id`` to be
  supplied to :func:`evaluate_condition` — omitting them while using a
  ``relationship`` node is a caller wiring bug and raises
  ``InvalidRuleCondition`` immediately, not ``INDETERMINATE`` (that
  would hide a real defect as if it were a data-quality gap).

Operator catalog (all three-valued; a leaf whose field is absent from
the resource evaluates to ``INDETERMINATE`` for every operator except
``exists``/``not_exists``):

* Scalar: ``equals``, ``not_equals``, ``contains``, ``not_contains``,
  ``starts_with``, ``ends_with``
* Boolean/null: ``is_true``, ``is_false``, ``exists``, ``not_exists``,
  ``is_null``, ``is_not_null`` (``is_null`` is a *comparison* operator,
  not a presence operator — an absent field is not the same fact as a
  field collected with value ``None``; see ``KMS`` rotation handling in
  ``rules/aws/kms.yaml`` for the precedent this follows)
* Numeric: ``greater_than``, ``greater_than_or_equal``, ``less_than``,
  ``less_than_or_equal``
* Collection: ``in``, ``not_in``, ``contains_any``, ``contains_all``,
  ``any``, ``all``, ``none`` (the last three are quantifiers, not plain
  comparisons — see :func:`_evaluate_quantifier`)
* String: ``matches_regex`` (an invalid pattern is a rule-authoring bug
  and raises ``InvalidRuleCondition``, never ``INDETERMINATE``)
* Network: ``cidr_contains``, ``cidr_is_public``, ``cidr_is_private``,
  ``port_equals``, ``port_in_range``
* Temporal: ``age_gt_days``, ``age_gte_days``, ``age_lt_days`` — require
  an explicit ``as_of`` timestamp passed to :func:`evaluate_condition`;
  there is no fallback to ``datetime.now()`` inside the evaluator,
  preserving the same determinism invariant enforced everywhere else in
  this codebase (see ``domain.drift.diff_engine.DiffEngine``).
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from ipaddress import ip_address, ip_network
from typing import TYPE_CHECKING, Any, Callable, Mapping

from domain.resources.models import NormalizedResource
from domain.shared.enums import RelationshipType
from domain.shared.errors import InvalidRuleCondition
from domain.shared.identifiers import ResourceId

if TYPE_CHECKING:
    from domain.graph.models import ResourceGraph


class EvaluationResult(str, Enum):
    """The three-valued (Kleene) outcome of evaluating a condition."""

    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    INDETERMINATE = "indeterminate"


_MATCHED = EvaluationResult.MATCHED
_NOT_MATCHED = EvaluationResult.NOT_MATCHED
_INDETERMINATE = EvaluationResult.INDETERMINATE

# Closed registry of graph-context functions available to `source: graph`
# leaves. Empty by design (blueprint §9: "capacité posée, catalogue en
# retard sur elle") — superseded in practice by the `relationship` node
# for real cross-resource rules, but kept for backward compatibility.
GRAPH_FUNCTIONS: Mapping[str, Callable[..., EvaluationResult]] = {}


# ---------------------------------------------------------------------
# Operator implementations — each takes (value, expected) and returns
# EvaluationResult. Grouped by category only for readability; all live
# in one flat registry (_COMPARISON_OPERATORS) below.
# ---------------------------------------------------------------------


def _op_equals(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value == expected else _NOT_MATCHED


def _op_not_equals(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value != expected else _NOT_MATCHED


def _op_greater_than(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value > expected else _NOT_MATCHED


def _op_greater_than_or_equal(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value >= expected else _NOT_MATCHED


def _op_less_than(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value < expected else _NOT_MATCHED


def _op_less_than_or_equal(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value <= expected else _NOT_MATCHED


def _op_contains(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if expected in value else _NOT_MATCHED


def _op_not_contains(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if expected not in value else _NOT_MATCHED


def _op_in(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value in expected else _NOT_MATCHED


def _op_not_in(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value not in expected else _NOT_MATCHED


def _op_starts_with(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value.startswith(expected) else _NOT_MATCHED


def _op_ends_with(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if value.endswith(expected) else _NOT_MATCHED


def _op_is_true(value: Any, _expected: Any) -> EvaluationResult:
    return _MATCHED if value is True else _NOT_MATCHED


def _op_is_false(value: Any, _expected: Any) -> EvaluationResult:
    return _MATCHED if value is False else _NOT_MATCHED


def _op_is_null(value: Any, _expected: Any) -> EvaluationResult:
    return _MATCHED if value is None else _NOT_MATCHED


def _op_is_not_null(value: Any, _expected: Any) -> EvaluationResult:
    return _MATCHED if value is not None else _NOT_MATCHED


def _op_matches_regex(value: Any, expected: Any) -> EvaluationResult:
    try:
        pattern = re.compile(expected)
    except re.error as exc:
        raise InvalidRuleCondition(f"invalid regex pattern {expected!r}: {exc}") from exc
    return _MATCHED if pattern.search(value) else _NOT_MATCHED


def _op_contains_any(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if any(item in value for item in expected) else _NOT_MATCHED


def _op_contains_all(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if all(item in value for item in expected) else _NOT_MATCHED


def _as_ip_network(value: Any):
    return ip_network(str(value), strict=False)


def _op_cidr_contains(value: Any, expected: Any) -> EvaluationResult:
    network = _as_ip_network(value)
    try:
        contained = ip_address(str(expected)) in network
    except ValueError:
        contained = _as_ip_network(expected).subnet_of(network)
    return _MATCHED if contained else _NOT_MATCHED


def _is_public_network(network) -> bool:
    return not (
        network.is_private
        or network.is_loopback
        or network.is_link_local
        or network.is_reserved
        or network.is_multicast
        or network.is_unspecified
    )


def _op_cidr_is_public(value: Any, _expected: Any) -> EvaluationResult:
    return _MATCHED if _is_public_network(_as_ip_network(value)) else _NOT_MATCHED


def _op_cidr_is_private(value: Any, _expected: Any) -> EvaluationResult:
    return _NOT_MATCHED if _is_public_network(_as_ip_network(value)) else _MATCHED


def _op_port_equals(value: Any, expected: Any) -> EvaluationResult:
    return _MATCHED if int(value) == int(expected) else _NOT_MATCHED


def _op_port_in_range(value: Any, expected: Any) -> EvaluationResult:
    low, high = expected
    return _MATCHED if low <= int(value) <= high else _NOT_MATCHED


# `exists`/`not_exists` are handled directly in `_evaluate_leaf` since they
# test presence, not the resolved value. `any`/`all`/`none` are handled by
# `_evaluate_quantifier` since they need a `where` sub-condition, not a
# `value`.
_COMPARISON_OPERATORS: Mapping[str, Callable[[Any, Any], EvaluationResult]] = {
    "equals": _op_equals,
    "not_equals": _op_not_equals,
    "greater_than": _op_greater_than,
    "greater_than_or_equal": _op_greater_than_or_equal,
    "less_than": _op_less_than,
    "less_than_or_equal": _op_less_than_or_equal,
    "contains": _op_contains,
    "not_contains": _op_not_contains,
    "in": _op_in,
    "not_in": _op_not_in,
    "starts_with": _op_starts_with,
    "ends_with": _op_ends_with,
    "is_true": _op_is_true,
    "is_false": _op_is_false,
    "is_null": _op_is_null,
    "is_not_null": _op_is_not_null,
    "matches_regex": _op_matches_regex,
    "contains_any": _op_contains_any,
    "contains_all": _op_contains_all,
    "cidr_contains": _op_cidr_contains,
    "cidr_is_public": _op_cidr_is_public,
    "cidr_is_private": _op_cidr_is_private,
    "port_equals": _op_port_equals,
    "port_in_range": _op_port_in_range,
}

_PRESENCE_OPERATORS = frozenset({"exists", "not_exists"})
_QUANTIFIER_OPERATORS = frozenset({"any", "all", "none"})
_TEMPORAL_OPERATORS = frozenset({"age_gt_days", "age_gte_days", "age_lt_days"})
_ALL_OPERATORS = (
    frozenset(_COMPARISON_OPERATORS) | _PRESENCE_OPERATORS | _QUANTIFIER_OPERATORS | _TEMPORAL_OPERATORS
)


# ---------------------------------------------------------------------
# Kleene combinators (unchanged since Phase 1)
# ---------------------------------------------------------------------


def _kleene_not(result: EvaluationResult) -> EvaluationResult:
    if result is _MATCHED:
        return _NOT_MATCHED
    if result is _NOT_MATCHED:
        return _MATCHED
    return _INDETERMINATE


def _kleene_and(results: list[EvaluationResult]) -> EvaluationResult:
    if not results:
        raise InvalidRuleCondition("'and' requires at least one operand")
    if any(r is _NOT_MATCHED for r in results):
        return _NOT_MATCHED
    if any(r is _INDETERMINATE for r in results):
        return _INDETERMINATE
    return _MATCHED


def _kleene_or(results: list[EvaluationResult]) -> EvaluationResult:
    if not results:
        raise InvalidRuleCondition("'or' requires at least one operand")
    if any(r is _MATCHED for r in results):
        return _MATCHED
    if any(r is _INDETERMINATE for r in results):
        return _INDETERMINATE
    return _NOT_MATCHED


def _existence_quantified_or(results: list[EvaluationResult]) -> EvaluationResult:
    """Same truth table as ``_kleene_or``, but a deliberately separate
    name: an *empty* input here (zero neighbors, zero collection
    elements) means "vacuously NOT_MATCHED" — a determinate fact, not
    an error — whereas an empty ``or`` in a rule's own ``condition`` tree
    is a rule-authoring bug (``_kleene_or`` raises on it). Quantifiers
    and relationships route here instead of ``_kleene_or`` for exactly
    that reason.
    """

    if not results:
        return _NOT_MATCHED
    return _kleene_or(results)


def _quantified_and(results: list[EvaluationResult]) -> EvaluationResult:
    """Same truth table as ``_kleene_and``, but an empty input is
    vacuously ``MATCHED`` (standard vacuous-truth semantics for "all
    elements of an empty collection satisfy X") rather than an error.
    """

    if not results:
        return _MATCHED
    return _kleene_and(results)


# ---------------------------------------------------------------------
# Field lookup (unchanged since Phase 1)
# ---------------------------------------------------------------------


def _lookup_field(data: Mapping[str, Any], field_path: str) -> tuple[bool, Any]:
    current: Any = data
    for part in field_path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"cannot interpret {value!r} as a timestamp")


def _evaluate_temporal(operator: str, value: Any, expected_days: Any, as_of: datetime | None) -> EvaluationResult:
    if as_of is None:
        raise InvalidRuleCondition(
            f"'{operator}' requires an explicit as_of timestamp — none was supplied to evaluate_condition()"
        )
    age_days = (as_of - _parse_timestamp(value)).total_seconds() / 86400
    if operator == "age_gt_days":
        return _MATCHED if age_days > expected_days else _NOT_MATCHED
    if operator == "age_gte_days":
        return _MATCHED if age_days >= expected_days else _NOT_MATCHED
    return _MATCHED if age_days < expected_days else _NOT_MATCHED  # age_lt_days


# ---------------------------------------------------------------------
# Leaf evaluation against an arbitrary mapping (resource attributes/tags,
# or — for quantifiers — one element of a collection field).
# ---------------------------------------------------------------------


def _evaluate_leaf_against_data(condition: Mapping[str, Any], data: Mapping[str, Any], as_of: datetime | None) -> EvaluationResult:
    field_path = condition["field"]
    operator = condition["operator"]

    if not isinstance(field_path, str) or not field_path:
        raise InvalidRuleCondition(f"'field' must be a non-blank string, got {field_path!r}")
    if operator not in _ALL_OPERATORS:
        raise InvalidRuleCondition(f"unknown operator: {operator!r}")

    present, value = _lookup_field(data, field_path)

    if operator == "exists":
        return _MATCHED if present else _NOT_MATCHED
    if operator == "not_exists":
        return _NOT_MATCHED if present else _MATCHED
    if operator in _QUANTIFIER_OPERATORS:
        return _evaluate_quantifier(operator, condition, present, value, as_of)

    if not present:
        return _INDETERMINATE

    if operator in _TEMPORAL_OPERATORS:
        try:
            return _evaluate_temporal(operator, value, condition.get("value"), as_of)
        except (TypeError, ValueError):
            return _INDETERMINATE

    expected = condition.get("value")
    try:
        return _COMPARISON_OPERATORS[operator](value, expected)
    except (TypeError, ValueError):
        # Incomparable/malformed data (e.g. `greater_than` on a string, a
        # non-CIDR value for a network operator) — the data exists but
        # cannot answer the question, so it's unknown, not false.
        return _INDETERMINATE


def _evaluate_quantifier(
    operator: str, condition: Mapping[str, Any], present: bool, value: Any, as_of: datetime | None
) -> EvaluationResult:
    if not present:
        return _INDETERMINATE
    if not isinstance(value, (list, tuple)):
        return _INDETERMINATE

    where = condition.get("where")
    if not isinstance(where, Mapping):
        raise InvalidRuleCondition(f"'{operator}' requires a 'where' sub-condition")

    element_results = [
        _evaluate_against_data(where, element, as_of) if isinstance(element, Mapping) else _INDETERMINATE
        for element in value
    ]

    if operator == "any":
        return _existence_quantified_or(element_results)
    if operator == "all":
        return _quantified_and(element_results)
    # "none" = NOT "any", computed directly (not via _kleene_not, so an
    # empty collection is MATCHED — "none of zero elements satisfy" is
    # vacuously true, the same reasoning as "all").
    any_result = _existence_quantified_or(element_results)
    return _kleene_not(any_result)


def _evaluate_against_data(condition: Mapping[str, Any], data: Mapping[str, Any], as_of: datetime | None) -> EvaluationResult:
    """Recursive evaluator used *inside* a quantifier's ``where`` clause,
    where there is no ``NormalizedResource`` — only a plain mapping (one
    element of a collection field). Supports ``and``/``or``/``not``,
    nested quantifiers, and leaves; deliberately rejects ``relationship``
    and ``source: graph`` nodes, which require real resource identity
    that a bare collection element doesn't have.
    """

    if not isinstance(condition, Mapping):
        raise InvalidRuleCondition(f"condition must be a mapping, got {type(condition).__name__}")

    if "relationship" in condition:
        raise InvalidRuleCondition("'relationship' conditions are not valid inside a quantifier's 'where' clause")
    if condition.get("source") == "graph":
        raise InvalidRuleCondition("'source: graph' conditions are not valid inside a quantifier's 'where' clause")

    if "and" in condition:
        return _kleene_and([_evaluate_against_data(c, data, as_of) for c in condition["and"]])
    if "or" in condition:
        return _kleene_or([_evaluate_against_data(c, data, as_of) for c in condition["or"]])
    if "not" in condition:
        return _kleene_not(_evaluate_against_data(condition["not"], data, as_of))
    if "field" in condition and "operator" in condition:
        return _evaluate_leaf_against_data(condition, data, as_of)

    raise InvalidRuleCondition(f"unrecognized condition shape: {condition!r}")


# ---------------------------------------------------------------------
# Resource-level leaf evaluation (attributes/tags/graph source)
# ---------------------------------------------------------------------


def _evaluate_leaf(condition: Mapping[str, Any], resource: NormalizedResource, as_of: datetime | None) -> EvaluationResult:
    source = condition.get("source", "attributes")
    if source == "attributes":
        data = resource.attributes
    elif source == "tags":
        data = resource.tags
    else:
        raise InvalidRuleCondition(f"unknown leaf source: {source!r}")

    return _evaluate_leaf_against_data(condition, data, as_of)


def _evaluate_graph_leaf(condition: Mapping[str, Any]) -> EvaluationResult:
    function_name = condition.get("function")
    if not isinstance(function_name, str) or function_name not in GRAPH_FUNCTIONS:
        raise InvalidRuleCondition(
            f"unregistered graph function: {function_name!r} (registry is currently empty)"
        )
    return GRAPH_FUNCTIONS[function_name](condition)  # pragma: no cover - unreachable today


def _evaluate_relationship(
    condition: Mapping[str, Any],
    resource: NormalizedResource,
    graph: "ResourceGraph | None",
    resources_by_id: Mapping[ResourceId, NormalizedResource] | None,
    as_of: datetime | None,
) -> EvaluationResult:
    if graph is None or resources_by_id is None:
        raise InvalidRuleCondition(
            "a 'relationship' condition requires both 'graph' and 'resources_by_id' to be "
            "supplied to evaluate_condition() — this is a caller wiring problem, not a data gap"
        )

    relationship_value = condition.get("relationship")
    try:
        relationship_type = RelationshipType(relationship_value)
    except ValueError:
        raise InvalidRuleCondition(f"unknown relationship type: {relationship_value!r}") from None

    direction = condition.get("direction")
    if direction not in ("outgoing", "incoming"):
        raise InvalidRuleCondition(f"'direction' must be 'outgoing' or 'incoming', got {direction!r}")

    where = condition.get("where")
    if not isinstance(where, Mapping):
        raise InvalidRuleCondition("a 'relationship' condition requires a 'where' sub-condition")

    target_type = condition.get("target_type")

    neighbors = graph.neighbors(resource.resource_id, relationship_type, direction=direction)
    if target_type is not None:
        neighbors = tuple(n for n in neighbors if n.resource_type == target_type)

    neighbor_results = []
    for neighbor in neighbors:
        neighbor_resource = resources_by_id.get(neighbor.resource_id)
        if neighbor_resource is None:
            neighbor_results.append(_INDETERMINATE)
            continue
        neighbor_results.append(evaluate_condition(where, neighbor_resource, graph=graph, resources_by_id=resources_by_id, as_of=as_of))

    return _existence_quantified_or(neighbor_results)


def evaluate_condition(
    condition: Mapping[str, Any],
    resource: NormalizedResource,
    *,
    graph: "ResourceGraph | None" = None,
    resources_by_id: Mapping[ResourceId, NormalizedResource] | None = None,
    as_of: datetime | None = None,
) -> EvaluationResult:
    """Recursively evaluate a raw condition dict against a resource.

    Deterministic: the same condition, resource, graph snapshot, and
    ``as_of`` always yield the same result. Raises
    ``InvalidRuleCondition`` for any structurally invalid condition
    (unknown operator, empty and/or, unrecognized shape, a
    ``relationship`` node used without ``graph``/``resources_by_id``, a
    temporal operator used without ``as_of``).

    ``graph``, ``resources_by_id``, and ``as_of`` are all optional and
    default to ``None`` — every condition tree that doesn't use a
    ``relationship`` node or a temporal operator behaves exactly as it
    did before this parameter set existed.
    """

    if not isinstance(condition, Mapping):
        raise InvalidRuleCondition(f"condition must be a mapping, got {type(condition).__name__}")

    if "and" in condition:
        return _kleene_and([evaluate_condition(c, resource, graph=graph, resources_by_id=resources_by_id, as_of=as_of) for c in condition["and"]])
    if "or" in condition:
        return _kleene_or([evaluate_condition(c, resource, graph=graph, resources_by_id=resources_by_id, as_of=as_of) for c in condition["or"]])
    if "not" in condition:
        return _kleene_not(evaluate_condition(condition["not"], resource, graph=graph, resources_by_id=resources_by_id, as_of=as_of))
    if "relationship" in condition:
        return _evaluate_relationship(condition, resource, graph, resources_by_id, as_of)
    if condition.get("source") == "graph":
        return _evaluate_graph_leaf(condition)
    if "field" in condition and "operator" in condition:
        return _evaluate_leaf(condition, resource, as_of)

    raise InvalidRuleCondition(f"unrecognized condition shape: {condition!r}")
