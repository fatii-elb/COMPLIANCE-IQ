"""Ports — the interfaces the domain and application depend on.

A *port* is an abstraction the business logic owns; an *adapter* in the
infrastructure layer implements it. This inversion (Dependency Inversion
Principle) is what keeps the core provider-agnostic: the application asks a
``Clock`` for the time or an ``LLMProvider`` for a completion without ever
knowing whether the clock is the system clock or which vendor answers the
completion.

Ports are introduced alongside the phase that first needs them:
- :class:`Clock`, :class:`HealthProbe` — Phase 1 (foundation).
- ``LLMProvider`` — Phase 2 (gateway & providers).
- ``VectorStore``, ``CorpusRepository`` — Phase 3 (RAG).
- ``FindingSource`` (Core API client) — Phase 6.
"""

from complianceiq.domain.ports.clock import Clock
from complianceiq.domain.ports.health import HealthProbe, HealthResult

__all__ = ["Clock", "HealthProbe", "HealthResult"]
