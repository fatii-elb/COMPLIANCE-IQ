"""``BuildResourceGraph`` (blueprint §4, formalizing the informal
``GraphBuilder.build()`` described in §10).

Pure orchestration: constructs a ``domain.graph.ResourceGraph`` from a
collection of ``NormalizedResource``s using only the Domain's own
``add_node``/``add_edge`` methods. Every invariant (tenant isolation,
referential integrity, closed relationship vocabulary) is enforced by
the Domain itself and surfaces here unmodified — this class adds no
validation of its own, per blueprint §10 ("qui le mute: personne après
construction") and the instruction not to duplicate Domain invariants.
"""

from __future__ import annotations

from typing import Iterable

from domain.graph.models import GraphEdge, GraphNode, ResourceGraph
from domain.resources.models import NormalizedResource
from domain.shared.identifiers import TenantId


class BuildResourceGraph:
    """Builds a tenant-scoped ``ResourceGraph`` from normalized resources."""

    def build(self, *, tenant_id: TenantId, resources: Iterable[NormalizedResource]) -> ResourceGraph:
        resources = list(resources)
        graph = ResourceGraph(tenant_id=tenant_id)

        for resource in resources:
            graph.add_node(
                GraphNode(
                    resource_id=resource.resource_id,
                    tenant_id=resource.tenant_id,
                    resource_type=resource.resource_type,
                )
            )

        # Edges are added only after every node exists, so relationship
        # order in the input never matters and add_edge's own
        # referential-integrity check is the single source of truth.
        for resource in resources:
            for relationship in resource.relationships:
                graph.add_edge(
                    GraphEdge(
                        source_id=resource.resource_id,
                        target_id=relationship.target_resource_id,
                        relationship_type=relationship.relationship_type,
                        # ResourceRelationship carries no "blocked" signal —
                        # determining which relationships are actually
                        # blocked is unspecified by the blueprint beyond
                        # the graph's own field (see Known Limitations).
                    )
                )

        return graph
