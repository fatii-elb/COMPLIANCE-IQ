"""AWS EC2 instance -> ``NormalizedResource`` (blueprint §6/§24, Phase 3).

Attached security groups become ``ATTACHED_TO`` relationships to the
security group's own ``NormalizedResource`` — both are real,
already-collected resources in the same scan, so this never risks the
``__internet__``/``GraphIntegrityViolation`` problem documented in
``normalizers/s3.py``. No VPC/subnet graph relationship is created:
the closed ``RelationshipType`` vocabulary (blueprint §10) has no
``CONTAINS``-for-network-topology precedent specified for this case,
and inventing one isn't necessary — ``vpc_id``/``subnet_id`` are
captured as plain attributes instead.
"""

from __future__ import annotations

from datetime import datetime

from domain.resources.models import NormalizedResource, ResourceRelationship
from domain.shared.enums import CloudProvider, RelationshipType
from domain.shared.identifiers import ResourceId, TenantId


def normalize_ec2_instance(
    *,
    instance_id: str,
    state: str,
    region: str,
    vpc_id: str | None,
    subnet_id: str | None,
    security_group_ids: tuple[str, ...],
    public_ip: str | None = None,
    instance_profile_arn: str | None = None,
    imds_v2_required: bool = False,
    root_volume_encrypted: bool | None = None,
    tags: dict[str, str],
    tenant_id: TenantId,
    collected_at: datetime,
    account_id: str | None = None,
) -> NormalizedResource:
    relationships = tuple(
        ResourceRelationship(
            target_resource_id=ResourceId(group_id),
            relationship_type=RelationshipType.ATTACHED_TO,
        )
        for group_id in security_group_ids
    )

    return NormalizedResource(
        resource_id=ResourceId(instance_id),
        resource_type="ec2_instance",
        cloud_provider=CloudProvider.AWS,
        tenant_id=tenant_id,
        region=region,
        attributes={
            "state": state,
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "public_ip": public_ip,
            "instance_profile_arn": instance_profile_arn,
            "imds_v2_required": imds_v2_required,
            # `None` when the root device isn't an EBS volume (e.g. an
            # instance-store-backed AMI) — encryption doesn't apply,
            # which is a different fact than "unencrypted".
            "root_volume_encrypted": root_volume_encrypted,
        },
        tags=tags,
        relationships=relationships,
        collected_at=collected_at,
        account_id=account_id,
    )
