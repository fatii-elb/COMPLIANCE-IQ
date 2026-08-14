"""The :class:`NormalizedResource` contract.

Produced by the Core Service's scanner/normalizer and consumed by this service.
A normalized resource is a cloud object (an S3 bucket, an IAM role, a VNet)
flattened into a provider-agnostic shape so downstream compliance logic does not
branch on cloud-specific payloads.
"""

from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.value_objects.enums import CloudProvider
from complianceiq.domain.value_objects.identifiers import NonEmptyStr, ResourceId, TenantId


class NormalizedResource(FrozenModel):
    """A cloud resource normalized into a provider-agnostic shape.

    Attributes:
        id: Stable resource identifier within the tenant.
        tenant_id: Owning tenant. Scopes all access.
        cloud: Originating cloud provider.
        service: Provider service name (e.g. ``s3``, ``iam``, ``storage``).
        region: Cloud region the resource lives in.
        type: Resource type (e.g. ``bucket``, ``role``).
        config: The normalized configuration payload. Free-form by design —
            different resource types carry different attributes — but always a
            JSON-serialisable mapping.
        collected_at: When the scanner observed this state (timezone-aware UTC).
    """

    id: ResourceId
    tenant_id: TenantId
    cloud: CloudProvider
    service: NonEmptyStr
    region: NonEmptyStr
    type: NonEmptyStr
    config: dict[str, Any]
    collected_at: AwareDatetime
