# Architecture

This document describes the layering, boundaries, and dependency rules of the
ComplianceIQ AI Service. It is the reference for *where code belongs* and *what
may depend on what*. The rules here are enforced automatically in CI by
import-linter (`.importlinter`), so they cannot silently decay.

## Clean Architecture layers

The service is organised in four concentric layers. Dependencies point **inward
only**: an outer layer may depend on an inner layer, never the reverse.

```mermaid
flowchart TD
    subgraph Presentation["presentation — FastAPI delivery"]
        P1[routers]
        P2[schemas]
        P3[errors]
    end
    subgraph Infrastructure["infrastructure — adapters"]
        I1[config]
        I2[logging]
        I3[http middleware]
        I4[clock]
    end
    subgraph Application["application — use cases"]
        A1[ReadinessService]
        A2[AppInfo]
    end
    subgraph Domain["domain — pure core"]
        D1[entities / contracts]
        D2[value objects]
        D3[ports]
        D4[policies]
        D5[exceptions]
    end

    P1 --> A1
    P1 --> D1
    I1 --> A2
    I3 --> I2
    A1 --> D3
    A1 --> D1
    Presentation -.wired at.-> Root((composition root))
    Infrastructure -.wired at.-> Root
```

### Domain (`complianceiq.domain`)
The enterprise core. Entities (the Section 6 contracts), value objects (enums,
`Citation`, identifiers), ports (`Clock`, `HealthProbe`), policies (tenant
isolation), and the typed exception hierarchy. **Imports only the standard
library and Pydantic** — enforced by the `domain-is-pure` contract. This purity
is what makes the business rules testable in isolation and independent of any
framework or vendor.

### Application (`complianceiq.application`)
Use cases that orchestrate the domain through ports. `ReadinessService`
aggregates health probes; later phases add enrichment, copilot, remediation, and
report use cases. **May import the domain, nothing outer** — enforced by
`application-is-framework-free`. `mypy --strict` runs on this layer and the
domain.

### Infrastructure (`complianceiq.infrastructure`)
Adapters to the outside world: configuration (`pydantic-settings`), structured
logging (structlog), ASGI middleware, the system clock, and — in later phases —
the SQLAlchemy repositories, the Anthropic provider, the pgvector store, and the
Core API client. Each adapter implements a domain port.

### Presentation (`complianceiq.presentation`)
The HTTP delivery mechanism (FastAPI): routers, wire schemas, and the single
exception-to-HTTP mapping. Thin by design — no business logic.

## The independence of the two adapter layers

`presentation` and `infrastructure` are **sibling** adapters; neither imports the
other (`adapters-are-independent` contract). Presentation needs wired services,
but it must not reach into infrastructure. This is resolved two ways:

1. **A structural `Container` protocol** (`presentation/container.py`) declares
   *what* presentation needs (application services and DTOs). The concrete
   container built at the composition root satisfies it structurally.
2. **Cross-cutting infrastructure** (logging/correlation middleware) is attached
   to the app by the composition root, not imported by presentation.

## The composition root (`complianceiq.composition`)

The single place — outside all four layers — allowed to import from both
infrastructure and presentation. It constructs concrete adapters, assembles the
`ApplicationContainer`, builds the FastAPI app, and attaches middleware. The
entire dependency graph is visible in this one file; there are no global
singletons or service locators.

```mermaid
sequenceDiagram
    participant Main as __main__ / asgi
    participant Comp as composition.build_app
    participant Infra as infrastructure
    participant Pres as presentation.create_app
    Main->>Comp: build_app(settings)
    Comp->>Infra: configure_logging()
    Comp->>Comp: build_container() → clock, readiness, app_info
    Comp->>Pres: create_app(container)
    Comp->>Infra: add middleware (correlation, size-limit)
    Comp-->>Main: FastAPI app
```

## Request lifecycle (Phase 1)

```mermaid
sequenceDiagram
    participant Client
    participant MW as CorrelationIdMiddleware
    participant Size as RequestSizeLimitMiddleware
    participant Router as health router
    participant Svc as ReadinessService
    Client->>MW: GET /health/ready
    MW->>MW: assign correlation_id, bind logging context
    MW->>Size: forward
    Size->>Router: within size limit → forward
    Router->>Svc: check()
    Svc-->>Router: ReadinessReport
    Router-->>MW: 200/503 + body
    MW-->>Client: response (+ X-Correlation-ID), access log emitted
```

## Dependency rules (enforced)

| Contract | Rule |
|----------|------|
| `core-layers` | application → domain only |
| `domain-is-pure` | domain imports no inner layers, no adapter frameworks |
| `application-is-framework-free` | application imports no outer layers/frameworks |
| `adapters-are-independent` | presentation ⊥ infrastructure |

See `docs/ADR/` for the reasoning behind the significant choices.
