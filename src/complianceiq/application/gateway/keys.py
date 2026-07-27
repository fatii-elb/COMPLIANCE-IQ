"""Cache-key construction — tenant-scoped and content-addressed.

A cache key must satisfy two rules at once:

1. **Tenant-scoped:** the key *always* includes the tenant id, so one tenant can
   never read another tenant's cached answer (non-negotiable rule 1 applied to
   the cache).
2. **Content-addressed:** identical inputs (messages, task, params, feature)
   produce the same key, so equivalent requests hit the cache — and any
   difference produces a different key, so stale answers are never served.

The key is a SHA-256 hash of a canonical JSON encoding of those inputs, so it is
stable regardless of dict ordering.
"""

from __future__ import annotations

import hashlib
import json

from complianceiq.domain.llm.requests import LLMRequest


def build_cache_key(tenant_id: str, request: LLMRequest) -> str:
    """Return a stable, tenant-scoped cache key for ``request``.

    Args:
        tenant_id: The acting tenant. Included so keys never collide across
            tenants.
        request: The high-level request whose content addresses the key.
    """
    payload = {
        "tenant": tenant_id,
        "task": request.task.value,
        "feature": request.feature,
        "params": request.params.model_dump(mode="json"),
        "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"ai:completion:{tenant_id}:{digest}"
