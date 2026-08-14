"""Real async sleeper adapter.

Implements the :class:`Sleeper` port with ``asyncio.sleep``. It exists as a port
so retry backoff can be tested instantly with a fake that records requested
delays instead of actually waiting.
"""

from __future__ import annotations

import asyncio

from complianceiq.domain.ports.gateway import Sleeper


class AsyncSleeper(Sleeper):
    """A :class:`Sleeper` backed by ``asyncio.sleep``."""

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
