"""ComplianceIQ AI Subsystem.

An independently deployable FastAPI service that turns raw multi-cloud security
findings into grounded, cited, audit-ready compliance intelligence. It is the
"Intelligence & Experience" half of the ComplianceIQ platform; the "Platform &
Data" half (scanning, rule engine, scoring, auth issuance) is a separate service
consumed over versioned REST.

The package is organised in four Clean Architecture layers with a strict inward
dependency rule (see ``.importlinter`` and ``docs/ARCHITECTURE.md``):

- :mod:`complianceiq.domain` — entities, value objects, ports, policies. Pure.
- :mod:`complianceiq.application` — use cases orchestrating the domain.
- :mod:`complianceiq.infrastructure` — adapters (config, logging, DB, providers).
- :mod:`complianceiq.presentation` — the HTTP delivery mechanism (FastAPI).

The two adapter layers are wired together only at the composition root,
:mod:`complianceiq.composition`.
"""

__version__ = "0.1.0"
