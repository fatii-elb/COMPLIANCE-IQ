"""The Resource Graph (blueprint §10).

``ResourceGraph`` is a tenant-scoped aggregate: it owns its nodes and
edges, enforces tenant isolation at ``add_node``, and enforces
referential integrity at ``add_edge`` (an edge can never reference a node
that does not exist). Nobody mutates it after a scan builds it — there is
no incremental-mutation API beyond ``add_node``/``add_edge`` themselves,
matching blueprint §10 ("qui le mute: personne après construction").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from domain.shared.enums import RelationshipType
from domain.shared.errors import GraphIntegrityViolation
from domain.shared.identifiers import ResourceId, TenantId
from domain.tenants.isolation import ensure_same_tenant


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A resource represented inside a ``ResourceGraph``."""

    resource_id: ResourceId
    tenant_id: TenantId
    resource_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.resource_type, str) or not self.resource_type.strip():
            raise GraphIntegrityViolation("GraphNode.resource_type must be a non-blank string")


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """A directed relationship between two nodes, using the closed
    ``RelationshipType`` vocabulary (blueprint §10). ``blocked`` records
    whether the relationship is prevented in practice (e.g. a security
    group rule that denies rather than allows) — attack path discovery
    relies on this flag.
    """

    source_id: ResourceId
    target_id: ResourceId
    relationship_type: RelationshipType
    blocked: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.relationship_type, RelationshipType):
            raise GraphIntegrityViolation(
                f"relationship_type must be a RelationshipType, got {self.relationship_type!r}"
            )


@dataclass(slots=True)
class ResourceGraph:
    """A tenant-scoped, in-memory resource graph.

    Lives for the duration of a single scan (blueprint §10: rebuilt every
    time, never persisted in the Domain). Not frozen — it is a mutable
    aggregate built incrementally by its owner, but every mutation goes
    through an invariant-checking method.
    """

    tenant_id: TenantId
    _nodes: dict[ResourceId, GraphNode] = field(default_factory=dict, repr=False)
    _edges: list[GraphEdge] = field(default_factory=list, repr=False)

    @property
    def nodes(self) -> tuple[GraphNode, ...]:
        return tuple(self._nodes.values())

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        return tuple(self._edges)

    def has_node(self, resource_id: ResourceId) -> bool:
        return resource_id in self._nodes

    def get_node(self, resource_id: ResourceId) -> GraphNode:
        try:
            return self._nodes[resource_id]
        except KeyError:
            raise GraphIntegrityViolation(f"no node for resource_id {resource_id!s}") from None

    def add_node(self, node: GraphNode) -> None:
        ensure_same_tenant(self.tenant_id, node.tenant_id, context="graph node")
        if node.resource_id in self._nodes:
            raise GraphIntegrityViolation(
                f"duplicate node: {node.resource_id!s} is already present in this graph"
            )
        self._nodes[node.resource_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.source_id not in self._nodes:
            raise GraphIntegrityViolation(
                f"edge references unknown source node: {edge.source_id!s}"
            )
        if edge.target_id not in self._nodes:
            raise GraphIntegrityViolation(
                f"edge references unknown target node: {edge.target_id!s}"
            )
        self._edges.append(edge)

    def neighbors(
        self,
        resource_id: ResourceId,
        relationship_type: RelationshipType,
        *,
        direction: Literal["outgoing", "incoming"],
    ) -> tuple[GraphNode, ...]:
        """Nodes directly connected to ``resource_id`` by an edge of
        exactly ``relationship_type``, in the given ``direction``.

        Read-only, one hop only — deliberately not a general traversal
        API (no path-finding, no depth parameter). An unknown
        ``resource_id`` or a node with no matching edges both return an
        empty tuple, never an error: "no relationship exists" is a
        determinate fact about the graph, not a failure.
        """

        if direction == "outgoing":
            matches = (e.target_id for e in self._edges if e.source_id == resource_id and e.relationship_type == relationship_type)
        else:
            matches = (e.source_id for e in self._edges if e.target_id == resource_id and e.relationship_type == relationship_type)

        return tuple(self._nodes[node_id] for node_id in matches if node_id in self._nodes)
