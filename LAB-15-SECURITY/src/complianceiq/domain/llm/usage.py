"""Usage-accounting value object.

Every model call emits a :class:`UsageEvent` recording *who* spent *how much* on
*what*. The gateway writes these to a :class:`~complianceiq.domain.ports.gateway.UsageLedger`
so cost can be attributed per tenant, per feature, and per model — and so a
tenant's spend can be checked against a budget before an expensive call.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import AwareDatetime, Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.llm.responses import TokenUsage
from complianceiq.domain.value_objects.identifiers import NonEmptyStr, TenantId


class UsageEvent(FrozenModel):
    """One accountable model call.

    Attributes:
        tenant_id: The tenant charged for the call.
        feature: The product feature that made the call.
        provider: The provider used.
        model_id: The model used.
        usage: Token counts.
        cost_usd: Computed billing cost in USD.
        cached: True if the response was served from cache (usually cost 0).
        occurred_at: When the call happened (timezone-aware UTC).
    """

    tenant_id: TenantId
    feature: NonEmptyStr
    provider: ProviderName
    model_id: NonEmptyStr
    usage: TokenUsage
    cost_usd: Decimal = Field(ge=Decimal(0))
    cached: bool = False
    occurred_at: AwareDatetime
