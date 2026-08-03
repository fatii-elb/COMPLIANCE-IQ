# ComplianceIQ — Backend Source Code Architecture

**Document class:** Source Code Architecture Specification (companion to the SAS)
**Scope:** Complete folder/package/file structure of the Cloud Compliance Intelligence Engine backend
**Language/runtime:** Python 3.13, Poetry, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Neo4j, Redis, RabbitMQ, Pydantic v2, Docker, pytest
**Style:** Clean Architecture + DDD + Hexagonal (Ports & Adapters) + SOLID + Event-Driven + Plugin Architecture
**Status:** Structure only — no implementation code, per instructions.

---

## 0. Organizing Principle

Two orthogonal axes organize this codebase, and every folder below belongs to exactly one cell of this grid:

1. **Layer axis** (Clean Architecture ring): `domain` → `application` → `infrastructure`, plus a `foundation` layer that sits beside all three (cross-cutting technical concerns with no business meaning) and an `api`/`jobs` layer that is the outermost Interface Adapters shell.
2. **Bounded-Context axis** (from the SAS Part 3 Bounded Context Map): Tenancy, Discovery, Normalization/URM, Graph, Policy, Context, Risk, Confidence, AttackPath, Compliance, Finding, Plugin, Eventing.

`domain/`, `application/`, and `infrastructure/` are each internally subdivided **by bounded context** (not by technical accident), so that `domain/risk/` and `application/risk/` and `infrastructure/risk/` (where infrastructure needs exist) all correspond to the same SAS module. The twelve **Engines** named in the prompt (Discovery Engine, Knowledge Graph Engine, Policy Intelligence Engine, etc.) are not a fourth parallel layer — each Engine's files are distributed across `domain/<context>/`, `application/<context>/`, and `infrastructure/<context>/` according to the Dependency Rule from SAS Part 2. This section explains that distribution once; the tree below shows the result.

Root package name: `complianceiq` (importable as `from complianceiq.domain.finding.entities import Finding`, etc.)

---

## 1. Repository Root

```
complianceiq-backend/
├── pyproject.toml
├── poetry.lock
├── alembic.ini
├── docker-compose.yml
├── docker-compose.override.yml
├── Dockerfile
├── Dockerfile.worker
├── Makefile
├── .env.example
├── .importlinter.cfg
├── .pre-commit-config.yaml
├── README.md
├── src/
│   └── complianceiq/
│       ├── __init__.py
│       ├── main.py
│       ├── foundation/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/
│       ├── plugins/
│       ├── eventing/
│       ├── api/
│       ├── jobs/
│       └── observability/
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
└── docs/
```

| File | Purpose |
|---|---|
| `pyproject.toml` | Poetry project manifest; declares all dependencies (fastapi, sqlalchemy, alembic, neo4j, redis, aio-pika/celery, pydantic, uvicorn, pytest, import-linter, ruff, mypy) and the `complianceiq` console entry point. |
| `alembic.ini` | Alembic migration tool configuration; points at `infrastructure.persistence.sqlalchemy` metadata and the `alembic/` script location. |
| `docker-compose.yml` | Local multi-container topology: `api`, `worker`, `postgres`, `neo4j`, `redis`, `rabbitmq` services, mirroring SAS Part 2's Container Diagram. |
| `Dockerfile` / `Dockerfile.worker` | Two images: the FastAPI/API+per-stage-service image, and the background-worker (Celery/consumer) image — reflecting the independently-scalable services from SAS Part 2 Section 5. |
| `.importlinter.cfg` | Mechanically enforces the Dependency Rule (SAS Part 2, Section 9): `domain` cannot import `application`/`infrastructure`; `application` cannot import `infrastructure`. |
| `main.py` | FastAPI application factory entry point; wires the DI container (`foundation.di`) and mounts `api.routers`. |

---

## 2. `foundation/` — Cross-Cutting Technical Layer

Owns nothing business-meaningful; every file here could theoretically be reused on a completely different project. No file in `foundation/` may import from `domain/`, `application/`, or `infrastructure/` (it sits "beside," not "inside," the Clean Architecture rings), except `foundation.di`, which is explicitly the Composition Root and is the one place allowed to import everything (see Section 2.9).

```
foundation/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── environments.py
│   └── secrets_loader.py
├── di/
│   ├── __init__.py
│   ├── container.py
│   ├── providers_domain.py
│   ├── providers_application.py
│   └── providers_infrastructure.py
├── logging/
│   ├── __init__.py
│   ├── logger_factory.py
│   ├── structured_formatter.py
│   └── correlation.py
├── exceptions/
│   ├── __init__.py
│   ├── base_exceptions.py
│   ├── domain_exceptions.py
│   ├── application_exceptions.py
│   └── infrastructure_exceptions.py
├── constants/
│   ├── __init__.py
│   ├── urm_types.py
│   ├── relationship_types.py
│   ├── severity_levels.py
│   └── framework_ids.py
├── utils/
│   ├── __init__.py
│   ├── hashing.py
│   ├── time_utils.py
│   ├── uuid7.py
│   ├── retry.py
│   └── json_canonicalization.py
├── middleware/
│   ├── __init__.py
│   ├── correlation_id_middleware.py
│   ├── tenant_context_middleware.py
│   ├── error_handling_middleware.py
│   └── request_logging_middleware.py
├── security/
│   ├── __init__.py
│   ├── jwt_provider.py
│   ├── password_hasher.py
│   ├── rbac.py
│   └── vault_client_wrapper.py
└── validation/
    ├── __init__.py
    ├── pydantic_base_models.py
    └── custom_validators.py
```

### 2.1 `config/`
| File | Purpose | Public classes / Main methods | Depends on | Why it exists |
|---|---|---|---|---|
| `settings.py` | Root `Settings` Pydantic-v2 `BaseSettings` model — DB URLs, Neo4j URI, Redis URI, RabbitMQ URI, JWT secret ref, feature flags. | `class Settings(BaseSettings)`; `get_settings() -> Settings` (lru-cached) | `pydantic`, env vars | Single source of truth for all runtime configuration; consumed by `foundation.di` only, never imported directly by domain/application code (NFR-10). |
| `environments.py` | Enum of deployment environments (`local`, `dev`, `staging`, `prod`) and environment-specific settings overrides. | `class Environment(str, Enum)` | `settings.py` | Lets `docker-compose.override.yml` and CI select environment-appropriate config without branching application code. |
| `secrets_loader.py` | Resolves `vault_secret_path`-style references (SAS Part 3 `CloudProvider.vault_secret_path`) into actual secret values at runtime via the Vault client. | `class SecretsLoader`; `async def resolve(path: str) -> str` | `infrastructure.vault` (via DI, not direct import) | Keeps the *concept* of "a secret reference" in Foundation while the *mechanism* (Vault SDK) stays in Infrastructure — mirrors SAS ADR on secrets management (Part 1, NFR-08). |

### 2.2 `di/` (Composition Root)
| File | Purpose | Public classes / Main methods | Depends on | Why it exists |
|---|---|---|---|---|
| `container.py` | The single Composition Root; wires every Port interface (defined in `application/*/ports.py`) to its concrete Infrastructure implementation. | `class Container` (e.g. built on `dependency-injector` or a hand-rolled registry); `def build_container(settings: Settings) -> Container` | Everything (only file allowed to) | This is the one place in the entire codebase where the Dependency Inversion arrows from SAS Part 2 Section 2 are actually resolved into concrete object graphs — isolating this in one file makes the fitness-test exclusion list (in `.importlinter.cfg`) trivial to state. |
| `providers_domain.py` | Registers Domain-layer pure services (e.g. `RiskCalculationService`) that need no injected dependencies themselves. | Factory functions | `domain.*` | Separates "no-dependency" domain service registration from the more complex adapter wiring, for readability at 100k+ LOC scale. |
| `providers_application.py` | Registers Application-layer Use Case classes, injecting their required Ports. | Factory functions | `application.*` | Keeps Use Case wiring in its own file so adding a new Use Case never requires touching Infrastructure wiring. |
| `providers_infrastructure.py` | Registers concrete adapters (SQLAlchemy repos, Neo4j adapter, Redis cache, RabbitMQ publisher, cloud SDK adapters) against their Port interfaces. | Factory functions | `infrastructure.*` | Isolates the most volatile wiring (infrastructure technology choices change most often) in one file. |

### 2.3 `logging/`
| File | Purpose | Public classes | Why it exists |
|---|---|---|---|
| `logger_factory.py` | Produces pre-configured `structlog`/`logging` loggers with correlation-id binding. | `def get_logger(name: str) -> Logger` | Ensures every module logs in the same structured JSON shape, required by Observability (Part 16 of the SAS). |
| `structured_formatter.py` | JSON log formatter emitting `tenant_id`, `scan_id`, `event_id` fields when present in context. | `class StructuredFormatter(logging.Formatter)` | Machine-parseable logs feeding the ELK/Loki stack referenced in SAS Part 16. |
| `correlation.py` | `contextvars`-based correlation ID propagation across async call chains. | `def get_correlation_id()`, `def bind_correlation_id(id: str)` | Lets a single `scan_id`/`event_id` be threaded through logs without explicit parameter passing everywhere. |

### 2.4 `exceptions/`
| File | Purpose | Public classes | Why it exists |
|---|---|---|---|
| `base_exceptions.py` | `ComplianceIQError` root exception with an `error_code` and `context: dict`. | `class ComplianceIQError(Exception)` | Single exception root lets `error_handling_middleware.py` translate any exception to a consistent API error shape. |
| `domain_exceptions.py` | e.g. `InvalidRiskScoreError`, `UnsupportedUrmTypeError`, `CircularCompositeRuleError` (SAS Part 5, Section 5.7). | Exception classes | Domain layer must be able to raise business-rule violations without importing HTTP or DB exception types. |
| `application_exceptions.py` | e.g. `UseCaseValidationError`, `RuleNotFoundError`. | Exception classes | Distinct from domain exceptions since these represent orchestration/use-case-level failures, not business-rule violations. |
| `infrastructure_exceptions.py` | e.g. `ProviderRateLimitExceeded`, `VaultUnreachableError`, `GraphStoreTimeoutError` (SAS Part 4/5 failure tables). | Exception classes | Infrastructure-specific failure taxonomy, caught and translated at Adapter boundaries per SAS failure-scenario tables. |

### 2.5 `constants/`
Mirrors the enums defined conceptually in SAS Part 3 (`urm_type`, `relationship_type`, `severity_band`) and Part 1 (`Framework` IDs) as single-sourced Python enums, so no module hardcodes string literals like `"ObjectStorage"` independently.

### 2.6 `utils/`
| File | Purpose | Why it exists |
|---|---|---|
| `hashing.py` | SHA-256 canonical content hashing (`content_hash`, `evidence_hash`, `snapshot_hash` from SAS Part 3). | Centralizes the exact hashing algorithm so `Rule`, `Evidence`, `Finding`, `HistoricalSnapshot` all hash identically — a re-derivability (NFR-05) requirement. |
| `time_utils.py` | UTC-aware timestamp helpers; a single `now()` function that all domain services call (never `datetime.now()` directly), enabling deterministic replay in tests. | |
| `uuid7.py` | UUIDv7 (time-ordered) generator, per SAS Part 3 Section 2's identity convention. | |
| `retry.py` | Generic exponential-backoff-with-jitter decorator, used by Discovery Engine adapters (SAS Part 4, Section 2.4). | |
| `json_canonicalization.py` | Deterministic JSON serialization (sorted keys, fixed float formatting) required before hashing. | Without canonicalization, semantically identical JSON could hash differently, breaking NFR-05. |

### 2.7 `middleware/`
FastAPI ASGI middleware: correlation ID injection, tenant-context extraction from the JWT (feeding `NFR-07` tenant isolation), global exception→HTTP-response translation, and structured request/response logging.

### 2.8 `security/`
| File | Purpose | Why it exists |
|---|---|---|
| `jwt_provider.py` | Issues/validates JWTs for the REST API (`api/` layer authentication). | |
| `rbac.py` | Role-based authorization checks (GRC Analyst / Security Engineer / Platform Engineer / Admin, per SAS Part 1 personas). | |
| `vault_client_wrapper.py` | Thin wrapper around the HashiCorp Vault client SDK, implementing the concrete side of `SecretsLoader` (Section 2.1). | Kept in `security/` rather than `infrastructure/` because it is a cross-cutting technical concern used by both Discovery (credentials) and Auth (secrets) — a deliberate exception justified in an ADR in SAS Part 15. |

### 2.9 `validation/`
Shared Pydantic base classes (`StrictBaseModel` forbidding extra fields) and custom field validators (CIDR validation, ARN validation) reused across Application-layer DTOs and API-layer request/response schemas.

---

## 3. `domain/` — Innermost Layer (Entities, Value Objects, Domain Services)

No file under `domain/` imports anything from `application/`, `infrastructure/`, `api/`, `jobs/`, `plugins/` (as concrete loader), or any third-party framework beyond `pydantic`/`attrs`/stdlib. This is mechanically enforced by `.importlinter.cfg` (SAS Part 2, Section 9).

```
domain/
├── __init__.py
├── shared/
│   ├── __init__.py
│   ├── value_objects.py
│   ├── entity_base.py
│   └── domain_event_base.py
├── tenancy/
│   ├── __init__.py
│   ├── entities.py
│   ├── value_objects.py
│   └── repositories.py
├── discovery/
│   ├── __init__.py
│   ├── entities.py
│   └── repositories.py
├── urm/
│   ├── __init__.py
│   ├── entities.py
│   ├── resource_types.py
│   ├── schemas.py
│   └── repositories.py
├── graph/
│   ├── __init__.py
│   ├── entities.py
│   ├── attack_path_entity.py
│   ├── traversal_service.py
│   ├── attack_path_search_service.py
│   └── repositories.py
├── policy/
│   ├── __init__.py
│   ├── entities.py
│   ├── composite_rule_entity.py
│   ├── rule_matching_service.py
│   ├── composite_rule_matching_service.py
│   └── repositories.py
├── context/
│   ├── __init__.py
│   ├── context_policy_entity.py
│   ├── context_resolution_service.py
│   └── repositories.py
├── risk/
│   ├── __init__.py
│   ├── risk_score_entity.py
│   ├── confidence_value_object.py
│   ├── risk_calculation_service.py
│   ├── attack_path_risk_calculation_service.py
│   └── repositories.py
├── confidence/
│   ├── __init__.py
│   ├── confidence_calculation_service.py
│   └── evidence_quality_policy.py
├── compliance/
│   ├── __init__.py
│   ├── entities.py
│   ├── mapping_service.py
│   └── repositories.py
├── drift/
│   ├── __init__.py
│   ├── historical_snapshot_entity.py
│   ├── drift_comparison_service.py
│   └── repositories.py
├── finding/
│   ├── __init__.py
│   ├── entities.py
│   ├── finding_status_policy.py
│   └── repositories.py
├── plugin/
│   ├── __init__.py
│   ├── entities.py
│   └── repositories.py
└── events/
    ├── __init__.py
    ├── discovery_events.py
    ├── normalization_events.py
    ├── graph_events.py
    ├── policy_events.py
    ├── risk_events.py
    ├── compliance_events.py
    ├── drift_events.py
    └── finding_events.py
```

### 3.1 `shared/`
| File | Purpose | Public classes | Why it exists |
|---|---|---|---|
| `value_objects.py` | Generic, reusable Value Objects: `Arn`, `CloudRegion`, `Severity`, `EvidenceHash`, `ContentHash` (SAS Part 3, Section 2). | `class Arn`, `class CloudRegion`, `class Severity(Enum)` | Every bounded context needs these; centralizing avoids N duplicate definitions. |
| `entity_base.py` | Abstract base for all Entities: enforces `id: UUID`, `created_at: datetime`, equality-by-identity. | `class Entity(ABC)` | Encodes the Entity-vs-Value-Object distinction (SAS Part 3, Section 2) as an actual type distinction, not just documentation. |
| `domain_event_base.py` | Abstract base for all Domain Events: `event_id`, `event_type`, `causation_id`, `emitted_at` (SAS Part 3, Section 3.19). | `class DomainEvent(ABC, Generic[T])` | Single canonical event envelope shape shared by every context-specific event module in `domain/events/`. |

### 3.2 `tenancy/`
| File | Purpose | Public classes | Why it exists |
|---|---|---|---|
| `entities.py` | `Tenant`, `CloudProvider`, `Scan` entities (SAS Part 3, Sections 3.1–3.2, 3.18), as frozen/attrs dataclasses. | `class Tenant(Entity)`, `class CloudProvider(Entity)`, `class Scan(Entity)` | Root bounded context; nearly every other entity references `tenant_id`. |
| `value_objects.py` | `RetentionPolicy`, `ScanStatus` enum, `TriggerSource` enum. | | |
| `repositories.py` | **Interfaces only** — `TenantRepository(Protocol)`, `CloudProviderRepository(Protocol)`, `ScanRepository(Protocol)` — abstract methods only, no implementation. | `class TenantRepository(Protocol): def get(self, id: UUID) -> Tenant: ...` | This is the Port; the concrete `infrastructure/persistence/repositories/tenant_repository_impl.py` implements it (Dependency Inversion, SAS Part 2 Section 7). |

### 3.3 `discovery/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `Resource` entity (SAS Part 3, Section 3.3) — raw, provider-native, immutable. | `class Resource(Entity)` |
| `repositories.py` | `ResourceRepository(Protocol)` port. | |

### 3.4 `urm/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `NormalizedResource` entity (SAS Part 3, Section 3.4). | `class NormalizedResource(Entity)` |
| `resource_types.py` | `UrmType` enum and the per-type attribute schema classes from SAS Part 4, Section 4.3 (`ObjectStorageAttributes`, `ComputeInstanceAttributes`, `IdentityPrincipalAttributes`, `DatabaseInstanceAttributes`, `AuditLogSinkAttributes`, `NetworkBoundaryAttributes`). | `class UrmType(Enum)`, one class per attribute schema |
| `schemas.py` | Pydantic validation schemas used to validate `security_attributes` JSONB against the correct per-`urm_type` shape at Normalization time (SAS Part 4, Section 3.7's schema-validation failure scenario). | `class ObjectStorageAttributesSchema(BaseModel)` etc. |
| `repositories.py` | `NormalizedResourceRepository(Protocol)`. | |

### 3.5 `graph/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `Relationship` entity (SAS Part 3, Section 3.5). | `class Relationship(Entity)` |
| `attack_path_entity.py` | `AttackPath` entity (SAS Part 3, Section 3.12). | `class AttackPath(Entity)` |
| `traversal_service.py` | Pure graph traversal primitives: neighbor lookup, N-hop reachability — used by both Policy graph-predicates (SAS Part 5 Section 4.5) and Attack Path search. | `class GraphTraversalService`; `def get_neighbors(...)`, `def get_reachable_resources(...)` |
| `attack_path_search_service.py` | The weighted-shortest-path search algorithm and composite risk formula from SAS Part 8, Sections 2.4–2.5. | `class AttackPathSearchService`; `def weighted_shortest_path(...)`, `def calculate_attack_path_risk(...)` |
| `repositories.py` | `RelationshipRepository(Protocol)`, `AttackPathRepository(Protocol)`, `GraphStorePort(Protocol)` (abstract graph-query interface, implemented by Neo4j adapter). | |

### 3.6 `policy/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `Policy`, `Rule` entities (SAS Part 3, Sections 3.6–3.7). | `class Policy(Entity)`, `class Rule(Entity)` |
| `composite_rule_entity.py` | `CompositeRule` entity (recursive structure, SAS Part 3 Section 3.8). | `class CompositeRule(Entity)` |
| `rule_matching_service.py` | Pure condition-tree evaluator (SAS Part 5, Section 4.5's `evaluate_condition_tree`). | `class RuleMatchingService`; `def evaluate(rule, resource, graph) -> Outcome` |
| `composite_rule_matching_service.py` | Recursive AND/OR/NOT/THRESHOLD evaluator (SAS Part 5, Section 5.4). | `class CompositeRuleMatchingService`; `def evaluate(composite, results) -> Outcome` |
| `repositories.py` | `RuleRepository(Protocol)`, `CompositeRuleRepository(Protocol)`, `PolicyRepository(Protocol)`. | |

### 3.7 `context/`
| File | Purpose | Public classes |
|---|---|---|
| `context_policy_entity.py` | `ContextPolicy` configuration entity (SAS Part 6, Section 3.4). | `class ContextPolicy(Entity)` |
| `context_resolution_service.py` | Pure resolution functions: `resolve_environment`, `resolve_data_classification`, `resolve_business_criticality`, `find_matching_compensating_control` (SAS Part 6, Section 3.5). | `class ContextResolutionService` |
| `repositories.py` | `ContextPolicyRepository(Protocol)`. | |

### 3.8 `risk/`
| File | Purpose | Public classes |
|---|---|---|
| `risk_score_entity.py` | `RiskScore` entity (SAS Part 3, Section 3.10). | `class RiskScore(Entity)` |
| `confidence_value_object.py` | `Confidence` Value Object (SAS Part 3, Section 3.11 — deliberately not an Entity). | `class Confidence` (frozen dataclass) |
| `risk_calculation_service.py` | The full multi-factor risk formula (SAS Part 7, Sections 2.4–2.6): `calculate_exploitability`, `calculate_blast_radius`, `calculate_data_sensitivity`, `calculate_business_criticality_factor`, `derive_severity_band`. | `class RiskCalculationService` |
| `attack_path_risk_calculation_service.py` | Separate service for the attack-path-specific formula (SAS Part 8, Section 2.5) — kept distinct from single-resource risk per SAS's explicit modeling decision. | `class AttackPathRiskCalculationService` |
| `repositories.py` | `RiskScoreRepository(Protocol)`. | |

### 3.9 `confidence/`
| File | Purpose | Public classes |
|---|---|---|
| `confidence_calculation_service.py` | The confidence formula (SAS Part 7, Section 4.3). | `class ConfidenceCalculationService` |
| `evidence_quality_policy.py` | Encodes which `Relationship.derived_from_rule` values count as "inferred vs observed" for evidence-quality penalty purposes. | `class EvidenceQualityPolicy` |

### 3.10 `compliance/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `Framework`, `ComplianceControl` entities (SAS Part 3, Sections 3.14–3.15). | `class Framework(Entity)`, `class ComplianceControl(Entity)` |
| `mapping_service.py` | Pure mapping/rollup aggregation logic (SAS Part 8, Section 4.4), independent of persistence. | `class ComplianceMappingService` |
| `repositories.py` | `FrameworkRepository(Protocol)`, `ComplianceControlRepository(Protocol)`, `ComplianceRollupRepository(Protocol)`. | |

### 3.11 `drift/`
| File | Purpose | Public classes |
|---|---|---|
| `historical_snapshot_entity.py` | `HistoricalSnapshot` entity (SAS Part 3, Section 3.16). | `class HistoricalSnapshot(Entity)` |
| `drift_comparison_service.py` | Pure drift-comparison algorithm (full pseudocode delivered in SAS Part 9). | `class DriftComparisonService` |
| `repositories.py` | `HistoricalSnapshotRepository(Protocol)`. | |

### 3.12 `finding/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `Finding`, `Evidence` entities (SAS Part 3, Sections 3.9, 3.13). | `class Finding(Entity)`, `class Evidence(Entity)` |
| `finding_status_policy.py` | Encodes valid `FindingStatus` transitions (`open → acknowledged → resolved`, etc.) as an explicit state policy (SAS Part 3 `Finding.status`). | `class FindingStatusPolicy` |
| `repositories.py` | `FindingRepository(Protocol)`, `EvidenceRepository(Protocol)`. | |

### 3.13 `plugin/`
| File | Purpose | Public classes |
|---|---|---|
| `entities.py` | `Plugin` entity (SAS Part 3, Section 3.17). | `class Plugin(Entity)` |
| `repositories.py` | `PluginRepository(Protocol)`. | |

### 3.14 `events/`
One module per bounded context, containing the concrete `DomainEvent` subclasses corresponding to the SAS Part 1/13 event catalog (`ScanStarted`, `ResourcesDiscovered`, `ResourcesNormalized`, `GraphBuilt`, `RulesEvaluated`, `RiskCalculated`, `AttackPathsIdentified`, `ComplianceMapped`, `DriftDetected`, `FindingCreated`, `FindingPersisted`, `ScanCompleted`). These are pure data definitions (Domain concern per SAS Part 2 Section 2.1); their *publication mechanism* lives in `eventing/`.

---

## 4. `application/` — Use Cases, Ports, DTOs

May import `domain/` and its own `ports.py`, never `infrastructure/` concretely.

```
application/
├── __init__.py
├── shared/
│   ├── __init__.py
│   ├── use_case_base.py
│   ├── dto_base.py
│   └── unit_of_work.py
├── discovery/
│   ├── __init__.py
│   ├── run_scan_use_case.py
│   ├── discover_resources_use_case.py
│   ├── ports.py
│   └── dtos.py
├── normalization/
│   ├── __init__.py
│   ├── normalize_resources_use_case.py
│   ├── ports.py
│   └── dtos.py
├── graph/
│   ├── __init__.py
│   ├── build_knowledge_graph_use_case.py
│   ├── discover_attack_paths_use_case.py
│   ├── ports.py
│   └── dtos.py
├── policy/
│   ├── __init__.py
│   ├── evaluate_rules_use_case.py
│   ├── evaluate_composite_rules_use_case.py
│   ├── ports.py
│   └── dtos.py
├── context/
│   ├── __init__.py
│   ├── enrich_context_use_case.py
│   ├── ports.py
│   └── dtos.py
├── risk/
│   ├── __init__.py
│   ├── calculate_risk_use_case.py
│   ├── calculate_confidence_use_case.py
│   ├── ports.py
│   └── dtos.py
├── compliance/
│   ├── __init__.py
│   ├── map_to_frameworks_use_case.py
│   ├── ports.py
│   └── dtos.py
├── drift/
│   ├── __init__.py
│   ├── detect_drift_use_case.py
│   ├── ports.py
│   └── dtos.py
├── finding/
│   ├── __init__.py
│   ├── build_finding_use_case.py
│   ├── query_findings_use_case.py
│   ├── update_finding_status_use_case.py
│   ├── ports.py
│   └── dtos.py
├── plugin/
│   ├── __init__.py
│   ├── register_plugin_use_case.py
│   ├── ports.py
│   └── dtos.py
├── mappers/
│   ├── __init__.py
│   ├── resource_mapper.py
│   ├── finding_mapper.py
│   └── compliance_rollup_mapper.py
└── event_handlers/
    ├── __init__.py
    ├── on_resources_discovered_handler.py
    ├── on_resources_normalized_handler.py
    ├── on_graph_built_handler.py
    ├── on_rules_evaluated_handler.py
    ├── on_risk_calculated_handler.py
    ├── on_attack_paths_identified_handler.py
    ├── on_compliance_mapped_handler.py
    └── on_drift_detected_handler.py
```

### 4.1 `shared/`
| File | Purpose | Public classes |
|---|---|---|
| `use_case_base.py` | Generic `UseCase[TRequest, TResponse]` ABC with a single `execute()` entry point — enforces SRP at the orchestration level (SAS Part 2, Section 2.2). | `class UseCase(ABC, Generic[TRequest, TResponse])` |
| `dto_base.py` | Base Pydantic model for all cross-boundary DTOs. | `class DTO(BaseModel)` |
| `unit_of_work.py` | `UnitOfWork(Protocol)` port abstracting a transactional boundary spanning multiple repository calls within one Use Case. | `class UnitOfWork(Protocol): async def __aenter__/__aexit__/commit/rollback` |

### 4.2 `discovery/`
| File | Purpose | Depends on | Public classes |
|---|---|---|---|
| `run_scan_use_case.py` | Top-level orchestrator triggered by API/scheduler; creates the `Scan` entity and kicks off discovery for every `CloudProvider` under a `Tenant` (SAS Part 4, Section 2). | `domain.tenancy`, `ports.py` | `class RunScanUseCase(UseCase)` |
| `discover_resources_use_case.py` | Implements the discovery pseudocode of SAS Part 4, Section 2.4, calling the `ResourceDiscoveryPort` per `CloudProvider`/region/resource-type. | `domain.discovery`, `ports.py` | `class DiscoverResourcesUseCase(UseCase)` |
| `ports.py` | `ResourceDiscoveryPort(Protocol)` (abstract cloud-adapter contract), `SecretsVaultPort(Protocol)`. | — | Interfaces only |
| `dtos.py` | `DiscoverResourcesRequest`, `DiscoverResourcesResponse`. | | |

### 4.3 `normalization/`
| File | Purpose | Public classes |
|---|---|---|
| `normalize_resources_use_case.py` | Implements SAS Part 4, Section 3.4's `normalize_resource` orchestration, delegating actual field mapping to plugin-provided `ResourceMapper`s. | `class NormalizeResourcesUseCase(UseCase)` |
| `ports.py` | `ResourceMapperRegistryPort(Protocol)` (resolves a `ResourceMapper` by `provider_native_type`). | |

### 4.4 `graph/`
| File | Purpose | Public classes |
|---|---|---|
| `build_knowledge_graph_use_case.py` | Orchestrates SAS Part 5, Section 2.4 (observed + inferred + IAM-trust relationship phases), delegating provider-specific inference to `GraphInferencePlugin`. | `class BuildKnowledgeGraphUseCase(UseCase)` |
| `discover_attack_paths_use_case.py` | Orchestrates SAS Part 8, Section 2.4 (entry points → targets → weighted search), invoked after `RiskCalculated`. | `class DiscoverAttackPathsUseCase(UseCase)` |
| `ports.py` | `GraphInferencePlugin(Protocol)`. | |

### 4.5 `policy/`
| File | Purpose | Public classes |
|---|---|---|
| `evaluate_rules_use_case.py` | Orchestrates SAS Part 5, Section 4.5 — fetches active policy, filters resources by `urm_type`, delegates to `RuleMatchingService`. | `class EvaluateRulesUseCase(UseCase)` |
| `evaluate_composite_rules_use_case.py` | Orchestrates SAS Part 5, Section 5.4, consuming the in-process `RuleEvaluationResultCache`. | `class EvaluateCompositeRulesUseCase(UseCase)` |
| `ports.py` | `RuleEvaluationResultCachePort(Protocol)`. | |

### 4.6 `context/`
| File | Purpose | Public classes |
|---|---|---|
| `enrich_context_use_case.py` | Orchestrates SAS Part 6, Section 3.5. | `class EnrichContextUseCase(UseCase)` |

### 4.7 `risk/`
| File | Purpose | Public classes |
|---|---|---|
| `calculate_risk_use_case.py` | Orchestrates SAS Part 7, Section 2.6, invoking `RiskCalculationService` per violation. | `class CalculateRiskUseCase(UseCase)` |
| `calculate_confidence_use_case.py` | Orchestrates SAS Part 7, Section 4 (co-located, in-process, with risk calculation per the SAS's container grouping). | `class CalculateConfidenceUseCase(UseCase)` |

### 4.8 `compliance/`
| File | Purpose | Public classes |
|---|---|---|
| `map_to_frameworks_use_case.py` | Orchestrates SAS Part 8, Section 4.4's rollup aggregation. | `class MapToFrameworksUseCase(UseCase)` |

### 4.9 `drift/`
| File | Purpose | Public classes |
|---|---|---|
| `detect_drift_use_case.py` | Orchestrates the drift comparison algorithm (full detail in SAS Part 9) against the prior `HistoricalSnapshot`. | `class DetectDriftUseCase(UseCase)` |

### 4.10 `finding/`
| File | Purpose | Public classes |
|---|---|---|
| `build_finding_use_case.py` | Terminal assembly: combines Evidence + RiskScore + Confidence + ComplianceControl mappings into an immutable `Finding` (SAS Part 9's Finding Builder). | `class BuildFindingUseCase(UseCase)` |
| `query_findings_use_case.py` | Read-side query use case backing the API's `GET /findings` endpoint. | `class QueryFindingsUseCase(UseCase)` |
| `update_finding_status_use_case.py` | The one permitted mutation on an otherwise-immutable aggregate — appends to the status-history sub-table (SAS Part 3, Section 3.13). | `class UpdateFindingStatusUseCase(UseCase)` |

### 4.11 `plugin/`
| File | Purpose | Public classes |
|---|---|---|
| `register_plugin_use_case.py` | Validates and registers a new `Plugin` (signature verification delegated to a Port; SAS Part 15 Secure Plugin Loading). | `class RegisterPluginUseCase(UseCase)` |

### 4.12 `mappers/`
Application-layer object mappers translating between Domain entities and Application DTOs (never between Domain entities and API/ORM shapes directly — those live in `api/schemas` and `infrastructure/persistence/models` respectively, per the Interface Adapters boundary, SAS Part 2 Section 2.3).

### 4.13 `event_handlers/`
One handler per pipeline-stage event (SAS Part 1, Section 10's event chain). Each handler subscribes (via the `eventing` infrastructure) to one Domain Event and invokes the next stage's Use Case — this is the concrete mechanism realizing the event-driven pipeline sequencing shown in every SAS sequence diagram from Part 4 onward.

---

## 5. `infrastructure/` — Outermost Layer (Adapters + Frameworks & Drivers)

May import anything, including third-party SDKs. Implements every Port defined in `application/*/ports.py` and `domain/*/repositories.py`.

```
infrastructure/
├── __init__.py
├── persistence/
│   ├── __init__.py
│   ├── sqlalchemy/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── session_factory.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── tenancy_models.py
│   │   │   ├── resource_models.py
│   │   │   ├── policy_models.py
│   │   │   ├── finding_models.py
│   │   │   ├── compliance_models.py
│   │   │   ├── drift_models.py
│   │   │   └── plugin_models.py
│   │   └── unit_of_work_impl.py
│   └── repositories/
│       ├── __init__.py
│       ├── tenant_repository_impl.py
│       ├── cloud_provider_repository_impl.py
│       ├── scan_repository_impl.py
│       ├── resource_repository_impl.py
│       ├── normalized_resource_repository_impl.py
│       ├── rule_repository_impl.py
│       ├── composite_rule_repository_impl.py
│       ├── context_policy_repository_impl.py
│       ├── risk_score_repository_impl.py
│       ├── finding_repository_impl.py
│       ├── evidence_repository_impl.py
│       ├── framework_repository_impl.py
│       ├── compliance_control_repository_impl.py
│       ├── compliance_rollup_repository_impl.py
│       ├── historical_snapshot_repository_impl.py
│       └── plugin_repository_impl.py
├── graph_store/
│   ├── __init__.py
│   ├── neo4j_client.py
│   ├── neo4j_relationship_repository_impl.py
│   ├── neo4j_attack_path_repository_impl.py
│   └── graph_store_port_impl.py
├── cache/
│   ├── __init__.py
│   ├── redis_client.py
│   ├── rule_evaluation_result_cache_impl.py
│   ├── risk_score_cache_impl.py
│   └── rule_cache_impl.py
├── messaging/
│   ├── __init__.py
│   ├── rabbitmq_connection.py
│   ├── event_publisher_impl.py
│   └── event_subscriber_impl.py
├── cloud_connectors/
│   ├── __init__.py
│   ├── aws/
│   │   ├── __init__.py
│   │   ├── aws_resource_discovery_adapter.py
│   │   ├── aws_resource_mappers.py
│   │   └── aws_graph_inference_plugin.py
│   ├── azure/
│   │   ├── __init__.py
│   │   ├── azure_resource_discovery_adapter.py
│   │   ├── azure_resource_mappers.py
│   │   └── azure_graph_inference_plugin.py
│   ├── gcp/
│   │   └── (mirrors azure/ structure)
│   └── oci/
│       └── (mirrors azure/ structure)
├── external_apis/
│   ├── __init__.py
│   └── vulnerability_intel_client.py
├── storage/
│   ├── __init__.py
│   └── evidence_blob_storage.py
├── vault/
│   ├── __init__.py
│   └── hashicorp_vault_client.py
└── config/
    ├── __init__.py
    └── database_config.py
```

### 5.1 `persistence/sqlalchemy/`
| File | Purpose | Depends on |
|---|---|---|
| `base.py` | Declarative base class + naming convention for constraints/indexes. | `sqlalchemy` |
| `session_factory.py` | Async session/engine factory, reads `foundation.config.settings`. | `sqlalchemy`, `foundation.config` |
| `models/*.py` | SQLAlchemy ORM models — the *persistence shape*, deliberately distinct from Domain entities (SAS Part 2, Section 2.3: Repository implementations translate between the two). One module per bounded context, mirroring SAS Part 12's table groupings (current-state vs. historical/append-only tables). | `sqlalchemy` |
| `unit_of_work_impl.py` | Concrete `UnitOfWork` implementing `application.shared.unit_of_work.UnitOfWork` via a SQLAlchemy session/transaction. | `application.shared` (port), `sqlalchemy` |

### 5.2 `persistence/repositories/`
One file per Port defined in `domain/*/repositories.py`, e.g. `finding_repository_impl.py` implements `domain.finding.repositories.FindingRepository`, translating `Finding` Domain entities ↔ `FindingModel` SQLAlchemy rows. Every file in this folder has an identical shape: a class implementing exactly one Domain-layer `Protocol`, with `get`, `save`, `list`, `delete` (where applicable) methods, and an internal `_to_entity()`/`_to_model()` mapping pair.

### 5.3 `graph_store/`
| File | Purpose |
|---|---|
| `neo4j_client.py` | Low-level Neo4j driver session management. |
| `neo4j_relationship_repository_impl.py` | Implements `domain.graph.repositories.RelationshipRepository` using Cypher queries. |
| `neo4j_attack_path_repository_impl.py` | Implements `domain.graph.repositories.AttackPathRepository`. |
| `graph_store_port_impl.py` | Implements the abstract `GraphStorePort` used by `domain.graph.traversal_service` and `attack_path_search_service`, translating pure-Python traversal calls into Cypher — this is the concrete adapter behind SAS Part 2's `GraphStorePort` abstraction, and behind SAS Part 12's noted choice between PostgreSQL adjacency tables and a dedicated graph store (Neo4j chosen here per the technology list). |

### 5.4 `cache/`
Redis-backed implementations of the transient, in-scan caches referenced throughout the SAS (`RuleEvaluationResultCache`, SAS Part 5 Section 5.5; `RiskScoreCache`, SAS Part 7 Section 2.6) plus a `rule_cache_impl.py` caching parsed/compiled YAML rule condition trees (SAS module list: "Rule Cache") to avoid re-parsing YAML on every scan.

### 5.5 `messaging/`
| File | Purpose |
|---|---|
| `rabbitmq_connection.py` | Connection/channel management (`aio-pika`). |
| `event_publisher_impl.py` | Implements `application.*.ports.EventPublisherPort`; serializes `domain.events.*` DomainEvent subclasses to the `Event` envelope shape (SAS Part 3, Section 3.19) and publishes to the appropriate RabbitMQ exchange/routing key. |
| `event_subscriber_impl.py` | Consumes messages and dispatches to the correct `application/event_handlers/*` handler based on `event_type`. |

### 5.6 `cloud_connectors/`
One subpackage per provider, each implementing the same two Ports (`ResourceDiscoveryPort` and `ResourceMapperRegistryPort`'s per-type mappers) plus a `GraphInferencePlugin` — directly realizing the Liskov Substitution requirement from SAS Part 1, Section 8.3 and the plugin extensibility of SAS Part 14. Every provider subpackage has an identical internal shape so that adding OCI support (already stubbed) is a matter of filling in three files, never touching `domain/` or `application/`.

### 5.7 `vault/`
Concrete HashiCorp Vault SDK client, the implementation behind `application.discovery.ports.SecretsVaultPort` and `foundation.security.vault_client_wrapper`.

---

## 6. `plugins/` — Plugin Manager (Module 15)

Distinct from `infrastructure/cloud_connectors/`, which contains the *built-in* provider plugins — `plugins/` contains the generic *loading mechanism* itself (SAS Part 14).

```
plugins/
├── __init__.py
├── plugin_loader.py
├── plugin_registry.py
├── plugin_interfaces.py
├── plugin_contracts.py
├── plugin_discovery.py
├── version_compatibility.py
└── signature_verifier.py
```

| File | Purpose | Public classes |
|---|---|---|
| `plugin_loader.py` | Loads a `Plugin` entity's `entry_point` into an actual importable Python object at runtime (`importlib`-based). | `class PluginLoader` |
| `plugin_registry.py` | In-memory registry mapping `provider_type`/`framework_id`/`rule_pack_id` → loaded plugin instance; backs `ResourceMapperRegistryPort`, `GraphInferencePlugin` resolution, etc. | `class PluginRegistry` |
| `plugin_interfaces.py` | The abstract base classes every plugin type must implement: `CloudProviderAdapterInterface`, `FrameworkDefinitionInterface`, `RulePackInterface` — mirrors SAS Part 14's class diagrams. | `class CloudProviderAdapterInterface(Protocol)` etc. |
| `plugin_contracts.py` | JSON-Schema-based contract validation for plugin manifests (declares required methods/metadata a plugin must expose). | `class PluginContractValidator` |
| `plugin_discovery.py` | Scans a configured plugin directory / entry-point group for available plugins at startup. | `class PluginDiscoveryService` |
| `version_compatibility.py` | Checks a plugin's declared `version` against the core engine's compatibility matrix before loading (SAS Part 14 extensibility safeguards). | `class VersionCompatibilityChecker` |
| `signature_verifier.py` | Verifies `Plugin.signature` cryptographically before loading (SAS Part 15, Secure Plugin Loading). | `class SignatureVerifier` |

---

## 7. `eventing/` — Event Bus Infrastructure Shell

A thin, generic orchestration shell around `infrastructure/messaging/`, providing the Application-facing `EventPublisherPort`/dispatch mechanism referenced across every engine.

```
eventing/
├── __init__.py
├── event_dispatcher.py
├── subscriber_registry.py
└── integration_event_adapter.py
```

| File | Purpose |
|---|---|
| `event_dispatcher.py` | Central dispatch loop: receives a deserialized `Event` envelope, looks up the registered `application/event_handlers/*` handler(s), invokes them (async). |
| `subscriber_registry.py` | Declarative registration mapping `event_type` string → handler class, populated at DI container build time. |
| `integration_event_adapter.py` | Translates internal `DomainEvent`s into the external-facing `FindingCreated` integration event consumed by Subsystem B (SAS ADR-001) — the one file that knows about the Subsystem A/B boundary contract shape. |

---

## 8. `api/` — REST API (Interface Adapters, Presentation)

```
api/
├── __init__.py
├── app.py
├── dependencies.py
├── routers/
│   ├── __init__.py
│   ├── scans_router.py
│   ├── findings_router.py
│   ├── compliance_router.py
│   ├── plugins_router.py
│   ├── policies_router.py
│   └── health_router.py
├── controllers/
│   ├── __init__.py
│   ├── scans_controller.py
│   ├── findings_controller.py
│   ├── compliance_controller.py
│   └── plugins_controller.py
├── schemas/
│   ├── __init__.py
│   ├── scan_schemas.py
│   ├── finding_schemas.py
│   ├── compliance_schemas.py
│   └── error_schemas.py
├── auth/
│   ├── __init__.py
│   ├── auth_dependency.py
│   └── rbac_dependency.py
└── openapi/
    ├── __init__.py
    └── openapi_customization.py
```

| File | Purpose | Depends on |
|---|---|---|
| `app.py` | FastAPI app instance, middleware registration, router mounting. | `foundation.middleware`, all `routers/*` |
| `dependencies.py` | FastAPI `Depends()` providers pulling Use Cases out of `foundation.di.container`. | `foundation.di` |
| `routers/*.py` | Thin route declarations (`@router.post(...)`) with no business logic — delegate immediately to `controllers/*`. | `controllers/*` |
| `controllers/*.py` | Translate HTTP request schemas → Application DTOs → invoke Use Case → translate result → HTTP response schema. This is the Controller role of Interface Adapters (SAS Part 2, Section 2.3). | `application.*`, `schemas/*` |
| `schemas/*.py` | Pydantic request/response models — the *HTTP-facing* shape, distinct from both Domain entities and Application DTOs. | `pydantic` |
| `auth/*.py` | FastAPI dependency wrappers around `foundation.security.jwt_provider`/`rbac`. | `foundation.security` |
| `openapi_customization.py` | Customizes generated OpenAPI schema (tags, examples, security schemes) satisfying SAS NFR-13 (API stability/versioning documentation). | |

---

## 9. `jobs/` — Background Jobs / Workers

```
jobs/
├── __init__.py
├── celery_app.py
├── scheduled_scan_job.py
├── incremental_scan_job.py
├── compensating_control_expiry_job.py
├── plugin_health_check_job.py
└── retry_policies.py
```

| File | Purpose |
|---|---|
| `celery_app.py` | Celery application instance configured against RabbitMQ as broker / Redis as result backend. |
| `scheduled_scan_job.py` | Periodic task triggering `RunScanUseCase` per tenant per its configured schedule. |
| `incremental_scan_job.py` | Periodic, higher-frequency incremental scan task (SAS Part 17 performance target). |
| `compensating_control_expiry_job.py` | Daily job generating the `ExpiredCompensatingControl` warning findings described in SAS Part 6, Section 3.8. |
| `plugin_health_check_job.py` | Periodic verification that all registered plugins still load and pass signature verification. |
| `retry_policies.py` | Celery-level retry/backoff configuration, distinct from the in-request retry logic in `foundation.utils.retry`. |

---

## 10. `observability/`

```
observability/
├── __init__.py
├── metrics/
│   ├── __init__.py
│   ├── prometheus_metrics.py
│   └── scan_metrics.py
├── tracing/
│   ├── __init__.py
│   └── otel_tracer.py
├── health/
│   ├── __init__.py
│   └── health_check_service.py
└── grafana/
    └── dashboards/  (JSON dashboard definitions, not Python)
```

| File | Purpose |
|---|---|
| `prometheus_metrics.py` | Prometheus client registry: request counters, histogram latencies, per-stage scan duration. |
| `scan_metrics.py` | Business-level metrics specific to the pipeline: `scan_duration_seconds`, `findings_created_total`, `attack_paths_discovered_total`, mirroring SAS Part 16. |
| `otel_tracer.py` | OpenTelemetry tracer provider setup, instrumenting FastAPI, SQLAlchemy, and the Use Case layer via decorators. |
| `health_check_service.py` | Aggregates DB/Neo4j/Redis/RabbitMQ connectivity checks for the `health_router.py` endpoint and Kubernetes liveness/readiness probes. |

---

## 11. `tests/`

```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   ├── domain/        (mirrors domain/ package structure 1:1)
│   ├── application/    (mirrors application/ package structure 1:1)
│   └── infrastructure/ (mirrors infrastructure/, using fakes not real DBs)
├── integration/
│   ├── persistence/
│   ├── graph_store/
│   ├── messaging/
│   └── cloud_connectors/
├── functional/
│   ├── api/
│   └── end_to_end_pipeline/
├── fixtures/
│   ├── __init__.py
│   ├── tenant_fixtures.py
│   ├── resource_fixtures.py
│   ├── rule_fixtures.py
│   └── finding_fixtures.py
├── fakes/
│   ├── __init__.py
│   ├── fake_resource_discovery_adapter.py
│   ├── fake_resource_repository.py
│   ├── fake_event_publisher.py
│   └── fake_secrets_vault.py
└── testcontainers/
    ├── __init__.py
    └── postgres_neo4j_containers.py
```

| Folder | Purpose |
|---|---|
| `unit/` | Pure, no-I/O tests against `domain/` services (deterministic formula verification, e.g. asserting the exact Risk Score output for known inputs, per SAS NFR-05's replay-testability requirement) and `application/` Use Cases (mocked Ports). |
| `integration/` | Tests against real Postgres/Neo4j/RabbitMQ via `testcontainers`, verifying repository implementations correctly round-trip Domain entities. |
| `functional/` | Full HTTP-level tests against a running `api.app` instance; `end_to_end_pipeline/` runs a full discovery→finding pipeline against a fake cloud provider adapter to verify wiring. |
| `fixtures/` | Reusable pytest fixtures constructing valid `Tenant`, `Resource`, `Rule`, `Finding` test instances. |
| `fakes/` | Hand-written in-memory fake implementations of each Port (not mocks) — "Fake Collectors" / "Fake Repositories" named in the requirements — used across unit tests for fast, deterministic Use Case testing. |
| `testcontainers/` | Docker-based ephemeral Postgres/Neo4j instances for integration tests. |

---

## 12. `docs/`

```
docs/
├── architecture/
│   ├── sas/                  (the SAS Parts 1–17 markdown files)
│   └── source_architecture.md (this document)
├── adr/
│   ├── 0001-subsystem-boundary.md
│   ├── 0002-clean-architecture.md
│   ├── 0003-yaml-rules.md
│   ├── 0004-event-bus.md
│   └── 0005-postgres-persistence.md
├── developer_guide/
│   ├── getting_started.md
│   ├── adding_a_cloud_provider.md
│   ├── authoring_a_rule.md
│   └── running_tests.md
├── api/
│   └── openapi.json (generated artifact)
└── diagrams/
    ├── sequence/
    └── class/
```

Each ADR file corresponds 1:1 to the Architecture Decision Records already established in SAS Part 1, Section 11, kept alongside the code so they version together with implementation changes, per NFR-06's auditability philosophy applied reflexively to the architecture documentation itself.

---

## 13. Cross-Reference: SAS Module → Source Package Mapping

| SAS Module (Part 1, Section 9) | Domain package | Application package | Infrastructure package |
|---|---|---|---|
| 1. Discovery Engine | `domain/discovery` | `application/discovery` | `infrastructure/cloud_connectors/*` |
| 2. Normalization Engine | `domain/urm` | `application/normalization` | `infrastructure/cloud_connectors/*/*_mappers.py` |
| 3. Universal Resource Model | `domain/urm/resource_types.py`, `schemas.py` | — | — |
| 4. Knowledge Graph Engine | `domain/graph` | `application/graph` | `infrastructure/graph_store` |
| 5. Policy Intelligence Engine | `domain/policy` | `application/policy` | `infrastructure/persistence/repositories/rule_repository_impl.py`, `infrastructure/cache/rule_cache_impl.py` |
| 6. Composite Rule Engine | `domain/policy/composite_rule_*.py` | `application/policy/evaluate_composite_rules_use_case.py` | — |
| 7. Context Engine | `domain/context` | `application/context` | `infrastructure/persistence/repositories/context_policy_repository_impl.py` |
| 8. Risk Intelligence Engine | `domain/risk` | `application/risk` | `infrastructure/persistence/repositories/risk_score_repository_impl.py`, `infrastructure/cache/risk_score_cache_impl.py` |
| 9. Confidence Engine | `domain/confidence` | `application/risk/calculate_confidence_use_case.py` | — |
| 10. Attack Path Engine | `domain/graph/attack_path_*.py` | `application/graph/discover_attack_paths_use_case.py` | `infrastructure/graph_store/neo4j_attack_path_repository_impl.py` |
| 11. Compliance Mapping Engine | `domain/compliance` | `application/compliance` | `infrastructure/persistence/repositories/compliance_*_repository_impl.py` |
| 12. Drift Detection Engine | `domain/drift` | `application/drift` | `infrastructure/persistence/repositories/historical_snapshot_repository_impl.py` |
| 13. Finding Builder | `domain/finding` | `application/finding` | `infrastructure/persistence/repositories/finding_repository_impl.py`, `evidence_repository_impl.py` |
| 14. Persistence Layer | — | — | `infrastructure/persistence/*` |
| 15. Plugin Manager | `domain/plugin` | `application/plugin` | `plugins/*`, `infrastructure/persistence/repositories/plugin_repository_impl.py` |
| 16. API Layer | — | — | `api/*` |
| 17. Event Bus | `domain/events` | `application/event_handlers` | `eventing/*`, `infrastructure/messaging/*` |

---

## 14. Closing Note

This document specifies the complete backend source tree — every top-level package, every subpackage, and every file, each tagged with its owning Clean Architecture layer, its purpose, its public classes/interfaces, its dependencies, and its rationale, sufficient for a downstream implementation pass (by another engineer or another AI) to generate working code file-by-file without further architectural decisions needing to be made. No implementation code has been included, per the stated scope of this task. Every module named in the original requirements (Foundation, Domain, Application, Infrastructure, and all twelve named Engines through Documentation) has been accounted for and mapped to a concrete location in the tree, with Section 13 above providing the definitive SAS-to-source cross-reference.
