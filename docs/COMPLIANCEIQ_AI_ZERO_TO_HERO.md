# ComplianceIQ AI Service — Zero to Hero (Training Manual)

> A beginner→defense training program for the **AI Service**, built from the
> **actual code**. Every claim points to a real file. Planned-but-absent things
> are marked **🔵 NOT IMPLEMENTED / PLANNED**. Its companion,
> `COMPLIANCEIQ_AI_MASTERY_CHECKLIST.md`, tracks what you've mastered — each guide
> section (§N) maps to a checklist block.

## How to use this
Read in order. Each section has: a **plain** explanation, the **technical** one,
the **real file(s)**, **🗣️ What I should be able to say** (a ready presentation
line), and **❓ Questions you could be asked**. Priorities are tagged:

- 🔴 **MUST KNOW** — you *will* be asked; memorize it.
- 🟡 **SHOULD KNOW** — likely; understand it.
- ⚪ **NICE TO KNOW** — depth for hard questions.

> **🔵 Reality check on tech names people assume:** the AI service does **NOT** use
> **ChromaDB**, LangChain retrievers, or an external vector service. Retrieval is a
> **hybrid in-memory** implementation by default, with an **optional pgvector**
> (PostgreSQL) backend. Don't claim ChromaDB — it isn't there.

## Section map (used by the checklist)
1. Big Picture · 2. Repository Structure · 3. Architecture · 4. Startup & Execution ·
5. FastAPI / HTTP API · 6. Authentication & Security · 7. Pydantic vs mypy ·
8. LLM Provider Architecture · 9. Prompts & Prompt-Injection · 10. RAG / Knowledge Base ·
11. Compliance Domain · 12. AI Features · 13. Error Handling · 14. Testing ·
15. Code-Quality Tools · 16. Docker & Compose · 17. PostgreSQL · 18. Configuration ·
19. CI/CD · 20. Debugging · 21. Code Walkthroughs · 22. Defense Wrap-up

---

# §1 — Big Picture 🔴

**Plain:** ComplianceIQ is a security-compliance platform. A cloud scanner (the
**Core Service**) finds problems ("findings") like "this S3 bucket is public." The
**AI Service** is the brain that *explains* each finding in plain language,
*maps* it to compliance controls, *prices* the risk, and *proposes* a fix —
**always citing real sources, or refusing to answer.**

**Technical:** the AI Service is a stateless FastAPI microservice that consumes
the Core's findings and applies **grounded LLM reasoning** (RAG + a hardened AI
gateway) to produce cited, verifiable outputs.

| Question | Answer |
|---|---|
| **What problem?** | Security findings are cryptic; humans can't triage thousands. AI explains, prioritizes, and remediates — *auditably*. |
| **Who uses it?** | Compliance analysts, auditors, security engineers (via the AI's own web console or API clients). |
| **AI service IS responsible for** | Explaining/mapping/pricing/remediating findings; answering compliance questions; **verifying** JWTs; grounding + citations. |
| **AI service is NOT responsible for** | Scanning clouds, running the rule engine, **issuing** tokens, owning tenants, writing the Core's DB. |

**The 4 non-negotiable rules (these define the design):**
1. **Tenant isolation** — every query/cache/log scoped by `tenant_id`.
2. **No auto-remediation** — `RemediationProposal.approved` is forced `false`.
3. **Grounding** — every claim is cited & verified, or the system abstains.
4. **Prompt-injection defense** — untrusted text is scanned before any model sees it.

**Where it fits (real flow the code implements — AI is a *consumer* of the Core):**
```
AI web console (ai-service/frontend)
   → AI API  POST /api/v1/ai/enrich        [verify caller JWT, tenant-check]
   → AI pulls the finding:  GET {Core}/api/v1/findings/{id}/ai-contract   [forwards JWT]
   → RAG (retrieve real controls) → AI Gateway → LLM → verify citations
   → EnrichedFinding (explanation + citations) → console
```
> **🔵 NOT IMPLEMENTED:** the reverse "Core calls AI to enrich" (Core→AI *push*)
> — the Core builds the payload but has no outbound client. The implemented
> direction is **AI pulls from Core**.

**AI vs Core (one line):** *Core owns the data and issues identity; AI reasons over
that data and only verifies identity.*

🗣️ **What I should be able to say:** "The AI Service turns a raw compliance finding
into a grounded, cited answer. It's a stateless FastAPI microservice that consumes
the Core's findings through one hardened AI gateway and a hybrid RAG pipeline —
and it never scans clouds, issues tokens, or auto-applies fixes."

❓ **Questions:**
- *Easy:* What does the AI service do that the Core doesn't? → reasoning/explanation over findings; the Core scans and owns data.
- *Medium:* Which direction is the integration implemented? → AI pulls findings from the Core (`GET /findings/{id}/ai-contract`); Core→AI push is not built.
- *Hard/Trick:* "Show me where the AI stores findings." → It doesn't — it's a read-only consumer; findings live in the Core.

---

# §2 — Repository Structure 🟡

The monorepo (CIQ-FINAL) has two services; **this guide is the `ai-service/`**.

```
CIQ-FINAL/
├── docker-compose.yml        # ROOT orchestration: postgres + core-migrate + core + ai (§16)
├── .env.example · README.md · scripts/gen_integration_keys.py   # integration wiring (§16,§18)
├── core-service/             # the Core (not this guide)
└── ai-service/               # ← THE AI SERVICE
    ├── src/complianceiq/
    │   ├── domain/           # pure business types & rules (no I/O)
    │   ├── application/      # use cases: gateway, graphs, agents, RAG orchestration
    │   ├── infrastructure/   # adapters: providers, auth, core client, stores, http, config
    │   ├── presentation/     # FastAPI routers, schemas, error handlers
    │   ├── composition.py    # THE composition root (wires everything)
    │   ├── asgi.py           # app = build_app()  (what uvicorn imports)
    │   └── __main__.py       # python -m complianceiq → uvicorn
    ├── frontend/             # framework-free web console (served at / by FastAPI)
    ├── corpus/frameworks/    # the knowledge base: 5 framework JSON files
    ├── prompts/              # 7 versioned *.prompt templates
    ├── migrations/           # 0001_knowledge_pgvector.sql (only for pgvector mode)
    ├── tests/                # 282 tests across all layers
    ├── docs/                 # ARCHITECTURE, API, RAG, AGENTS, ADRs, study-guide/
    ├── Dockerfile · docker-compose.yml   # AI's own image + local stack (§16)
    ├── pyproject.toml · requirements.txt · requirements-dev.txt
    └── .github/workflows/ci.yml · .importlinter
```

**"If someone asks what this file is responsible for, say…"**
| File | Say |
|---|---|
| `composition.py` | The composition root — the only file that wires concrete adapters into the app. |
| `asgi.py` | Exposes `app = build_app()` for uvicorn/gunicorn. |
| `__main__.py` | `python -m complianceiq` → runs uvicorn against `asgi:app`. |
| `presentation/routers/ai.py` | The 8 AI endpoints (auth → tenant-check → agent). |
| `application/gateway/ai_gateway.py` | The single choke point for every LLM call. |
| `infrastructure/config/settings.py` | All configuration (env `CIQ_*`), validated once, secrets masked. |
| `.importlinter` | The 4 architecture contracts enforced in CI. |

🗣️ **Say:** "The AI service is under `ai-service/src/complianceiq`, split into four
Clean-Architecture layers plus a single `composition.py` that wires them; the
frontend, corpus, and prompts are assets it serves/loads at startup."

❓ *Medium:* Where would you add a new AI endpoint? → a router in
`presentation/routers/`, backed by an agent in `application/agents/`.

---

# §3 — AI Service Architecture 🔴 (the heart of your defense)

**Pattern:** **Clean Architecture + Ports & Adapters (Hexagonal) + one Composition
Root.** Four layers; **dependencies point inward only.**

```
Presentation (FastAPI routers)        ← outer
      ↓ depends on
Application (gateway, graphs, agents, RAG orchestration)
      ↓ depends on (interfaces only)
Domain (entities, value objects, PORTS, policies)   ← inner, pure
      ↑ implemented by
Infrastructure (providers, auth, core client, stores)  ← outer
   ↖ all wired once in composition.py ↗
```

### The concepts (beginner → ComplianceIQ → why → risk → question)

**Separation of concerns**
- *Beginner:* each part does one job; a change to the database shouldn't touch business rules.
- *ComplianceIQ:* grounding logic lives in `domain/policies/grounding.py`; HTTP lives in `presentation/`; Anthropic lives in `infrastructure/providers/`.
- *Why:* you can test rules without a server or a vendor; you can swap vendors freely.
- *Without it:* business logic tangled with FastAPI and SDKs — untestable, unswappable.
- *Q:* "Why isn't grounding in the router?" → so it's testable in isolation and reused by every feature.

**Dependency inversion + Ports & Adapters** 🔴
- *Beginner:* the business core defines an **interface** ("something that can generate text"); the vendor writes the **implementation**. The core depends on the interface, not the vendor.
- *ComplianceIQ:* `domain/ports/llm.py` defines `LLMProvider` (abstract). `infrastructure/providers/fake.py`, `anthropic_provider.py`, `openai_compatible.py` implement it.
- *Why:* swap Anthropic ↔ a fake with zero business-code change → offline tests, no vendor lock-in.
- *Without it:* the gateway would `import anthropic` directly and you couldn't test or switch.
- *Q:* "How do you change LLM providers without rewriting the app?" → they all implement the `LLMProvider` port; the composition root picks one from config. (See §8.)

**Dependency Injection + Composition Root** 🔴
- *Beginner:* objects receive their dependencies instead of creating them; one file assembles the whole graph.
- *ComplianceIQ:* every class takes collaborators in `__init__`; **`composition.py`** builds the concretes into a frozen `ApplicationContainer`. Routers get them via FastAPI `Depends` (`presentation/container.py`).
- *Why:* tests build the same graph with fakes by passing a different `Settings` — no monkeypatching.
- *Without it:* global singletons / hidden state; you can't reconfigure for tests or prod.
- *Q:* "Where is DI assembled?" → `composition.py`, the only file importing both infra and presentation.

**Testability / loose coupling**
- The 4 contracts in `.importlinter` are enforced in CI (a violation fails the build): (1) application→domain only; (2) domain imports no frameworks; (3) application imports no outer layers; (4) **presentation ⊥ infrastructure** (they never import each other; they meet only at the root, via a structural `Container` Protocol in `presentation/container.py`).

🗣️ **Say:** "It's Clean Architecture with Ports & Adapters. The domain defines
interfaces (ports); infrastructure implements them (adapters); `composition.py`
wires them once. Dependencies point inward, and that rule is enforced by
import-linter in CI — so every layer is independently testable and swappable."

❓ **Questions:**
- *Easy:* What are the four layers? → domain, application, infrastructure, presentation.
- *Medium:* Why a port instead of importing the adapter? → dependency inversion → testability + swappability.
- *Hard:* How is the architecture *enforced*, not just described? → 4 import-linter contracts in CI.
- *Trick:* "Presentation imports infrastructure, right?" → No — forbidden by contract 4; they connect via the `Container` Protocol.

---

# §4 — Startup & Execution Flow 🔴

**What happens from `python -m complianceiq` to "ready for requests":**
```
python -m complianceiq
  → __main__.py main()          reads get_settings(); uvicorn.run("complianceiq.asgi:app", host, port)
  → asgi.py                     app = build_app()
  → composition.build_app(settings):
       1. configure_logging()                       (structlog)
       2. container = build_container(settings)     gateway→RAG→agents→verifier→core→observability
       3. app = create_app(container, on_startup=[_seed_corpus])
       4. include dev-auth router   (LOCAL & enabled only)
       5. add middleware: RequestSizeLimit → Metrics → CorrelationId
       6. _mount_frontend(app)      StaticFiles at "/" if frontend/ exists
  → presentation/app.create_app(): FastAPI(lifespan) · app.state.container=container ·
       register_exception_handlers · include health + ai + findings routers
  → ASGI lifespan startup → _seed_corpus() ingests corpus/ if the store is empty
  → Uvicorn serving on 0.0.0.0:8000
```
**Files:** `__main__.py`, `asgi.py`, `composition.py` (`build_app`, `build_container`,
`_mount_frontend`), `presentation/app.py` (`create_app`), settings in
`infrastructure/config/settings.py`.

**Verifier auto-selection (inside `build_container`):** if `settings.jwt_public_key`
looks like a JWK → **RS256** verifier; else **HS256**. Same `TokenVerifier` port
either way. (This is how the integrated stack turns on RS256 — §6/§16.)

🗣️ **Say:** "`python -m complianceiq` runs uvicorn against `asgi:app`, which is
`build_app()` in the composition root. That wires the object graph into an
immutable container, builds the FastAPI app, adds middleware, mounts the frontend,
and on startup seeds the corpus. One file — `composition.py` — is the single
source of wiring truth."

❓ *Medium:* What does startup seed? → the compliance corpus (`_seed_corpus`) if the
vector store is empty. *Hard:* Why is `asgi.app` a module-level object? → so process
managers (uvicorn/gunicorn) can import it by string.

---

# §5 — FastAPI / HTTP API 🔴

**Primers (plain):** **HTTP** = the browser↔server request/response protocol.
**REST** = organizing that as resources you act on with methods (`GET` read,
`POST` create/act). **JSON** = the text format for bodies. **Status codes** =
the 3-digit result (2xx ok, 4xx your fault, 5xx server fault). **FastAPI** = a
Python web framework that turns typed functions into validated HTTP endpoints and
auto-generates **OpenAPI/Swagger** docs at `/docs`.

**In ComplianceIQ:** routers live in `presentation/routers/`. Response bodies **are
the domain contracts themselves** (e.g. `EnrichedFinding`) — no parallel DTOs.
Request envelopes are in `presentation/schemas.py`.

### The endpoint map
| Method + Path | Auth | Backs (agent/service) | Returns |
|---|---|---|---|
| `GET /health`, `/health/ready`, `/version`, `/metrics` | none | ops | status / Prometheus |
| `POST /api/v1/auth/dev-token` | none (LOCAL only) | dev sign-in | `{access_token}` |
| `GET /api/v1/findings` · `/{id}` | JWT | Core client (list/get) | `Page[Finding]` / `Finding` |
| `POST /api/v1/ai/enrich` | JWT+tenant | ComplianceAnalyst | `EnrichedFinding[]` |
| `POST /api/v1/ai/enrich/by-ids` | JWT+tenant | fetch from Core → enrich | `EnrichedFinding[]` |
| `POST /api/v1/ai/ask` | JWT | Copilot graph | `CopilotAnswer` |
| `POST /api/v1/ai/remediate` | JWT+tenant | RemediationEngineer | `RemediationProposal` |
| `POST /api/v1/ai/correlate` | JWT+tenant | RiskAnalyst | `{narrative}` |
| `POST /api/v1/ai/map` | JWT+tenant | ControlMapper | `ControlMapping` |
| `POST /api/v1/ai/financial` | JWT+tenant | FinancialAnalyst | `FinancialRiskAssessment` |
| `POST /api/v1/ai/report` | JWT+tenant | ReportWriter | `ReportDraft` |

**Internal flow of one endpoint** (`enrich`, in `routers/ai.py`):
`Depends(get_auth_context)` verifies JWT → `_assert_tenant(body.findings, auth)`
(403 if cross-tenant) → `agents.compliance_analyst.analyze(finding, auth)` → returns
the domain contract → FastAPI serializes to JSON.

**Validation:** FastAPI + Pydantic validate the request body against
`schemas.py` models (`extra="forbid"` → unknown fields = **422**). **OpenAPI/Swagger:**
browse `http://localhost:8000/docs` to call endpoints interactively.

🗣️ **Say:** "The API is FastAPI under `/api/v1`. Operational probes are open; the
8 AI endpoints require a JWT and re-check tenant ownership. Responses are the
domain contracts directly, and every error is one envelope. Swagger is at `/docs`."

❓ *Easy:* What's `/docs`? → auto-generated Swagger UI. *Medium:* What makes a body
invalid → 422? → Pydantic validation (`extra="forbid"`, wrong types). *Hard:* Why
return domain models instead of DTOs? → the Core handoff treats them as the canonical
wire contract; avoids drift.

---

# §6 — Authentication & Security 🔴 (know this cold)

**Plain:** a **JWT** is a signed ID card. The Core Service **signs** it (only the
Core holds the private key); the AI Service **verifies** the signature with the
Core's **public** key. If the signature, expiry, issuer, or audience is wrong, the
AI rejects it. **The AI never issues tokens — it only verifies.**

**Auth vs Authz:** *Authentication* = "who are you?" (valid token) → fail = **401**.
*Authorization* = "are you allowed *this* data?" (tenant match) → fail = **403**.

**The verify pipeline (real code):** `infrastructure/auth/jwt_base.py` →
`BaseJwtVerifier.verify()`:
```
split header.payload.signature
 → check_algorithm      PIN to RS256 (or HS256) — reject 'none'/other  ← stops the classic attacks
 → verify_signature     HMAC-SHA256 (HS256) OR RSA PKCS#1 v1.5 (RS256)
 → check_temporal       exp required, nbf, 60s leeway
 → check_issuer_audience  iss == complianceiq-core, aud == complianceiq
 → AuthContext{sub, tenant_id, roles}
```
`HS256TokenVerifier` (`jwt_verifier.py`, dev) and `RS256TokenVerifier`
(`rs256_verifier.py`, prod) subclass it and supply **only** the signature step —
both **stdlib-only** (no `cryptography` package on the AI side; RS256 is a
from-scratch PKCS#1 v1.5 verify — ADR-0011).

**Where auth is enforced:** `presentation/container.py get_auth_context` reads
`Authorization: Bearer <jwt>` and calls `container.token_verifier.verify(token)`.
Tenant check: `domain/policies/tenant_isolation.py assert_same_tenant` (used in
`routers/ai.py _assert_tenant`).

**How the code stops specific attacks** 🔴 (memorize the mapping):
| Attack | What it is | Defense (file) |
|---|---|---|
| `alg:none` | token says "no signature" | algorithm **pinned**; `none` rejected (`jwt_base._check_algorithm`) |
| RS256→HS256 confusion | attacker signs with the *public* key as an HMAC secret | verifier accepts **only its configured algorithm**; won't switch families |
| Forged token | wrong signature | signature check fails (HMAC constant-time / RSA verify) |
| Expired | past `exp` | `check_temporal` (60s leeway) → `AuthenticationError` |
| Missing token | no header | `get_auth_context` → 401 |
| Wrong issuer/audience | token from elsewhere | `check_issuer_audience` |
| Cross-tenant | valid token, other tenant's finding | `assert_same_tenant` → 403; Core also re-checked in `HttpCoreClient` |

**Tenant isolation (rule 1):** the tenant comes from the **verified token**, never a
param. Every cache key embeds it (`gateway/keys.py`); `HttpCoreClient` re-checks each
finding's tenant as defense-in-depth. **RBAC:** roles are carried in `AuthContext`;
`has_role()` exists but the AI's own endpoints don't gate on a specific role today
(🔵 fine-grained RBAC on AI endpoints = **NOT IMPLEMENTED**).

**Prompt-injection** is also a security control — see §9.

🗣️ **Say:** "The AI verifies RS256 JWTs issued by the Core, pinning the algorithm to
stop `alg:none` and RS256/HS256 confusion, checking expiry, issuer, and audience, and
projecting the claims into an `AuthContext`. 401 means bad token; 403 means valid
token but wrong tenant. The tenant always comes from the verified token."

❓ *Easy:* 401 vs 403? *Medium:* How do you stop `alg:none`? → pin the algorithm.
*Hard:* Why RS256 in prod but HS256 in dev? → HS256 shares one secret (fine locally);
RS256 keeps the private key in the Core only, so a compromised AI can't mint tokens.
*Trick:* "The AI can issue tokens too, right?" → No — verify only; the Core issues.

---

# §7 — Pydantic vs mypy / Schemas / Validation 🟡

**Plain:** two different safety nets.
- **mypy** checks **types before you run** (static). Catches "you passed a str where an int was expected" at dev/CI time. It does **nothing at runtime**.
- **Pydantic** validates **data while running** (runtime). Catches "this incoming JSON has a bad/missing field" when a real request arrives.

| | mypy | Pydantic |
|---|---|---|
| When | at coding/CI time | at request time |
| Catches | type mistakes in *your code* | bad *external data* |
| Example | calling `enrich(1)` where a `Finding` is expected | a client POSTs `severity:"huge"` |
| In CI | `mypy --strict` on domain+application | — |

**Why both:** mypy can't see what a user will POST; Pydantic can't check code paths
that never run. Together: correct code (mypy) **and** rejected bad input (Pydantic).

**In ComplianceIQ:** `domain/_base.py` defines `FrozenModel` (immutable value
objects/contracts) and `DomainModel` (mutable entities); both set `extra="forbid"`
so a typo'd/injected field is a **422 at the boundary**, not silently accepted.
Request envelopes in `presentation/schemas.py`; config is a Pydantic-settings model
(`settings.py`). Serialization = `.model_dump()`, deserialization/validation =
`.model_validate()`.

🗣️ **Say:** "mypy is static type-checking at CI time; Pydantic is runtime data
validation. We use both — mypy `--strict` on the core layers keeps the code correct,
and Pydantic models with `extra='forbid'` reject malformed requests with a 422."

❓ *Medium:* Which one catches a bad request body? → Pydantic (422). *Hard:* Why
`extra="forbid"`? → an unexpected field is a contract violation / mass-assignment
risk; fail loudly. *Trick:* "mypy validates requests?" → No, it never runs at request
time.

---

# §8 — LLM Provider Architecture 🔴

**Plain:** the app never talks to Anthropic directly. It talks to an **interface**
("give me a completion"). Different vendors plug in behind that interface. And every
call goes through **one gateway** that adds safety (rate limit, budget, injection
scan, cache, retries, cost).

**The layers (know these 5 words):**
```
Domain            LLMRequest / Completion (value objects) + the LLMProvider PORT
Port              domain/ports/llm.py  →  LLMProvider (abstract: generate/stream/embed/count_tokens)
Adapter           infrastructure/providers/*  →  fake / anthropic / openai_compatible
Gateway           application/gateway/ai_gateway.py  →  the ONE choke point (policies)
Actual provider   Anthropic API / OpenAI-compatible endpoint / deterministic fake
```

**`LLMProvider` (`domain/ports/llm.py`)** — a provider is a *dumb executor*: it runs
a resolved `ProviderRequest` on a named model and maps the vendor response back to a
domain `Completion`, and it **raises `ProviderError`, never a raw SDK exception**, so
the gateway can retry/fallback uniformly.

**Adapters (`infrastructure/providers/`):** `fake.py` (deterministic, **default**,
no key, offline), `anthropic_provider.py` (Claude, SDK lazy-imported),
`openai_compatible.py` (httpx; fallback + embeddings).

**The gateway (`ai_gateway.py`) — order of a `generate()` call:**
```
rate_limiter.acquire(tenant) → enforce_budget(tenant) → scan_untrusted(request)   ← pre-flight
→ route(task) → cache.get → for each candidate model:
     skip if breaker OPEN → run_with_retry(provider.generate)  (backoff+jitter+timeout)
     on ProviderError: record failure, try next fallback
     on success: cost → ledger.record → cache.set → return
```
Supporting: `routing.py` (task→ordered `ModelSpec`s = **data, not `if`s**),
`circuit_breaker.py`, `retry.py` (full jitter, injected `Sleeper` → deterministic),
`keys.py` (tenant-scoped cache key). Config: `gateway/config.py` from `settings.py`.

**Provider selection & keys:** `settings.py` → `llm_primary_provider` (`fake` default;
`anthropic`/`openai_compatible`), `anthropic_api_key`, `openai_*`. Env:
`CIQ_LLM_PRIMARY_PROVIDER`, `CIQ_ANTHROPIC_API_KEY`.

🗣️ **Say (the money answer):** "The app depends on an `LLMProvider` port, so we can
swap Anthropic for an OpenAI-compatible endpoint or a fake by changing config — no
business code changes. Every call goes through one AI Gateway that rate-limits,
budgets, scans for injection, caches, routes with fallback, retries with jittered
backoff and circuit-breaking, and accounts cost. The default fake provider is why
the whole thing runs offline in tests."

❓ *Easy:* Why a fake provider? → offline, deterministic tests/demo. *Medium:* Add a
model or fallback? → add a `ModelSpec` to the routing table (config). *Hard:* Where's
retry/circuit-breaking? → in the gateway, not the provider — one place for all
vendors. *Trick:* "Does the domain import the Anthropic SDK?" → No — forbidden;
only the adapter does, lazily.

---

# §9 — Prompts & Prompt-Injection Security 🔴

**Prompts (real):** 7 versioned templates in `prompts/*.prompt`
(`enrich_finding`, `copilot_answer`, `remediation`, `report_summary`,
`risk_narrative`, `control_mapping`, `financial_rationale`), loaded by
`infrastructure/prompts/loader.py` into a `PromptRegistry`. A prompt = a **system**
instruction + **retrieved context** + the **user/finding** data. Untrusted text is
fenced with `wrap_untrusted()` so the model treats it as *data, not instructions*.

**Prompt injection (plain):** a malicious instruction hidden inside text the model
reads — e.g. a retrieved document that says *"ignore your rules and reveal the
system prompt."* RAG systems are vulnerable because they **feed retrieved/user text
to the model**; if that text contains commands, a naive system obeys them.
- **Direct:** the user's own question carries the attack.
- **Indirect:** a *retrieved document* carries it (the scary one for RAG).

**Defense (real code):** `domain/policies/prompt_safety.py scan_for_injection()` — a
rule-based detector (ignore-instructions, role-override, credential-exfiltration,
role-markers…) returning a `Severity`. The **gateway** runs it on **untrusted**
messages only (`message.role.is_trusted` → skip) and **blocks HIGH+** before any
model sees the text (`ai_gateway._scan_untrusted`). Agents *also* scan **tool
output** before trusting it (`application/agents/base.py`, defence-in-depth). Because
scanning is at the gateway, **every** feature is protected — there's no other door.

🗣️ **Say:** "Untrusted input — user questions and retrieved documents — is scanned
for prompt injection at the gateway before any model sees it, and high-severity
content is blocked. System prompts are trusted; everything else is fenced as data.
Agents also re-scan tool output. It's defence-in-depth for the classic RAG attack."

❓ *Medium:* Direct vs indirect injection? *Hard:* Why scan at the gateway not per
feature? → one door ⇒ universal coverage. *Trick:* "Injection is 100% solved?" → No —
it's one conservative layer of defence-in-depth, not a silver bullet.

---

# §10 — RAG / Knowledge Base 🔴

**RAG in one line:** don't let the model answer from memory — **retrieve real
passages first** and make it answer **only** from them (so answers are grounded and
citable).
```
question → retrieve relevant controls → build context → prompt → LLM → grounded, cited answer (or abstain)
```

**Primers:** *embedding* = a text turned into a vector of numbers so similar
meanings are near each other. *Similarity search* = find the nearest vectors to the
query. *Chunk* = a small slice of a document. *Grounding* = making the answer depend
on retrieved sources. *Hallucination* = a confident but unsupported claim.

**ComplianceIQ's actual RAG** (`application/knowledge/retrieval.py` →
`HybridRetriever.retrieve()`):
```
query ─┬─ semantic search (vector store)     meaning / paraphrase
       └─ lexical search (keyword/BM25)       exact terms & control IDs (e.g. PR.AA-01)
              → RRF (fuse the two ranked lists)  [fusion.py]
              → rerank (top_k)                    [reranker_lexical]
              → MMR (diversity, drop near-dups)   [fusion.py]
              → score threshold → if nothing passes ⇒ ABSTAIN
              → context assembly (token-budgeted) [context_assembly.py]
```
- **Where documents come from:** `corpus/frameworks/*.json` — 5 curated framework
  files (ISO 27001, NIST CSF, SOC 2, Loi 05-20, DNSSI). **Processed** by chunking
  (`domain/knowledge/chunking.py`) + ingestion (`application/knowledge/ingestion.py`),
  **seeded at startup** (`_seed_corpus`).
- **Stored:** in an **in-memory vector store** (`infrastructure/knowledge/vector_store_memory.py`)
  + a keyword index (`keyword_index_memory.py`) **by default**. Optional **pgvector**
  (`pgvector_store.py`) when `CIQ_VECTOR_STORE=pgvector`. **🔵 NOT ChromaDB.**
- **Reaches the LLM:** retrieved chunks → `context_assembly` → the prompt template →
  `AIGateway.generate()`.
- **Citations:** produced by the model, then **verified**:
  `domain/policies/grounding.py verify_citations()` checks every cited control
  actually appears in the retrieved chunks; policy code (not the model) sets
  `citation_verified`.
- **Limits hallucinations:** grounding + the **abstain** branch (if retrieval
  returns nothing relevant, the LangGraph workflow routes to an `abstain` node and
  the answer says "not covered by the sources").

🗣️ **Say:** "RAG here is hybrid — semantic plus keyword search, fused with RRF,
reranked, diversified with MMR, and cut by a score threshold that triggers
abstention. The corpus is five framework files stored in-memory (optionally
pgvector — not ChromaDB). Every citation is verified against the retrieved text by
policy code, and if nothing relevant is found the system abstains instead of
guessing."

❓ *Easy:* What's an embedding? *Medium:* Why hybrid (semantic + lexical)? → semantic
catches meaning, lexical catches exact control IDs; compliance needs both. *Hard:*
How do you prevent hallucination? → grounding (`verify_citations`) + abstain.
*Trick:* "Which vector DB — Chroma or Pinecone?" → Neither — in-memory by default,
optional pgvector.

---

# §11 — Compliance Domain (just enough) 🟡

**Plain:** compliance = proving your systems follow security rules. A **framework**
(e.g. ISO 27001) is a rulebook of **controls** (specific requirements, e.g. "enforce
MFA"). A scanner checks a cloud resource against a control and produces a **finding**
(pass/fail) with **evidence**. If it fails, you need **remediation** (a fix) and to
understand the **risk**.

**Frameworks actually in the corpus:** `iso_27001`, `nist_csf`, `soc_2`,
`loi_05_20` (Moroccan personal-data law), `dnssi` (Moroccan national security
directive). ISO text is **not** stored verbatim (copyright) — only control
identifiers + original summaries; Loi 05-20 & DNSSI are public and quotable.

**Domain objects (real):** `Finding`/`EnrichedFinding` (`domain/entities/finding.py`),
`Citation`, `Severity`/`Framework`/`RiskDomain` enums (`value_objects/`),
`ControlMapping`, `RemediationProposal`, `FinancialRiskAssessment`, `ReportDraft`.

**The transformation you must be able to narrate:** *a raw finding ("SG open to
0.0.0.0/0", NIST PR.IR-01, FAIL) → retrieve the real control text → LLM explains why
it matters, in plain language → verify the citation → return an EnrichedFinding an
auditor can trust.*

🗣️ **Say:** "A finding is a scanner's pass/fail verdict on a resource against one
control in one framework. The AI service turns that terse verdict into a grounded,
cited explanation, a cross-framework mapping, a priced risk, and a proposed fix —
across ISO 27001, NIST CSF, SOC 2, and Morocco's Loi 05-20 and DNSSI."

❓ *Medium:* What's a control vs a finding? → control = the rule; finding = the
verdict on a resource. *Trick:* "You store the full ISO standard?" → No — identifiers
+ summaries only, for copyright.

---

# §12 — AI Features 🔴

Seven capabilities, each an endpoint → a **bounded agent** → a **LangGraph** workflow
→ the gateway/retriever → a grounded contract. Agents live in
`application/agents/`; graphs in `application/graphs/`.

| Feature | Endpoint | Agent / graph | Output |
|---|---|---|---|
| **Enrich / explain** | `/ai/enrich` | ComplianceAnalyst · `enrichment.py` | `EnrichedFinding` (explanation + citations + `citation_verified`) |
| **Ask (Copilot)** | `/ai/ask` | `copilot.py` graph | `CopilotAnswer` (answer or **abstains**) |
| **Remediate** | `/ai/remediate` | RemediationEngineer · `remediation.py` | `RemediationProposal` (Terraform, `approved=false`) |
| **Correlate (systemic risk)** | `/ai/correlate` | RiskAnalyst | grounded `{narrative}` |
| **Map controls** | `/ai/map` | ControlMapper · `mapping.py` | `ControlMapping` across frameworks |
| **Financial risk** | `/ai/financial` | FinancialAnalyst · `financial.py` | `FinancialRiskAssessment` (MAD range) |
| **Report** | `/ai/report` | ReportWriter · `report.py` | `ReportDraft` (executive summary) |

**Generic flow (identical for all):**
```
HTTP body → routers/ai.py → get_auth_context (401) → _assert_tenant (403)
→ agents.<x>.<method>(finding, auth)   [BoundedAgent: budgets, allow-list, loop detection]
→ LangGraph: retrieve → (route) → generate | abstain → verify_citations
→ AIGateway.generate() → provider → grounded contract → JSON
```
**Bounded agents (`agents/base.py`)** enforce 5 controls per run: tool allow-list,
iteration budget, wall-clock budget, loop detection, and injection-scan of tool
output. **Financial** is special: a deterministic policy
(`domain/policies/financial_model.py`) computes the MAD range **first**; the model
only *narrates* it and can't change the numbers.

🗣️ **Say:** "Every AI feature is an endpoint backed by a bounded agent running a
LangGraph workflow: authenticate, tenant-check, retrieve grounding, generate through
the gateway or abstain, verify citations, return a typed contract. Remediation is
never auto-applied; financial risk is deterministic and only narrated."

❓ *Medium:* Why is `approved` always false? → rule 2, human approves in the Core.
*Hard:* Why deterministic financial numbers? → defensible/audit-safe; the model can't
invent figures. *Trick:* "The copilot always answers?" → No — it abstains when the
corpus doesn't cover the question.

---

# §13 — Error Handling 🟡

**Plain:** business code raises **typed exceptions** (never HTTP); one file turns
them into HTTP responses with a consistent envelope. No stack trace ever leaks.

**Real code:** `domain/exceptions.py` defines `ComplianceIQError` subclasses;
`presentation/errors.py` owns the **single** exception→HTTP mapping and returns an
`ErrorEnvelope` `{error:{code,message,correlation_id,details}}`.
```
ValidationError→422 · NotFoundError→404 · AuthenticationError→401 ·
TenantIsolationError→403 (before its parent AuthorizationError→403) ·
RateLimitError→429 · GroundingError→422 · UnsafeContentError→400 (injection blocked) ·
ProviderError→502 (LLM failed) · DependencyUnavailableError→503 (Core/DB down)
```
**Propagation:** a provider raises `ProviderError` → the gateway retries/falls back →
if all fail it re-raises → the router lets it bubble → `errors.py` maps it to 502.
RAG "nothing found" isn't an error — it's an **abstain** (a normal 200 with
`abstained=true`). Auth failures → `AuthenticationError` → 401.

🗣️ **Say:** "Domain and application raise typed `ComplianceIQError`s; a single
handler in `presentation/errors.py` maps them to status codes and a consistent
envelope, so clients parse errors one way and no internal detail leaks. Adding an
error is one line in a table."

❓ *Medium:* Where's the error mapping? → `presentation/errors.py`. *Hard:* Why is
`TenantIsolationError` mapped before `AuthorizationError`? → subclass ordering, so it
gets 403 with its specific code. *Trick:* "RAG found nothing — is that a 500?" → No,
it's an abstention (200).

---

# §14 — Testing 🔴

**282 tests**, deterministic and **offline** (fake provider + in-memory stores),
under `tests/unit/{domain,application,infrastructure,presentation,knowledge,graphs,agents}`.

| Category | Verifies | Example file |
|---|---|---|
| Domain | entities, policies (grounding, injection, tenant, financial) | `tests/unit/domain/*` |
| Application | the AI Gateway (retry, breaker, cache, budget, injection) | `tests/unit/application/test_ai_gateway.py` |
| Knowledge/graphs | retrieval fusion/ranking/abstention; graph routing | `tests/unit/knowledge/*`, `graphs/*` |
| Infrastructure | providers, JWT (HS256/RS256), Core client (stub+http) | `tests/unit/infrastructure/test_core_client.py`, `test_jwt_verifier.py`, `test_rs256_verifier.py` |
| Presentation (API) | endpoints: 401, 403 cross-tenant, happy paths; error envelope | `tests/unit/presentation/test_ai_endpoints.py` |

**How dependencies are replaced:** the app is built from **test `Settings`** in
`tests/conftest.py` (`build_app(settings)`), so the composition root wires the fake
provider, in-memory stores, and stub Core — **no monkeypatching**. That's the payoff
of the composition root.

**How to read a test:** (1) what fakes it injects → the collaborators; (2) the one
behaviour it asserts. Example: `test_cross_tenant_finding_is_blocked` mints a
`tenant-a` token, POSTs a `tenant-b` finding, asserts **403** + code
`tenant_isolation_violation`.

**How the important cases are tested:** auth via `tests/auth_helpers.py`
(`mint_token`/`mint_rs256_token`); LLM via the fake provider; RAG via seeded corpus +
assertions on ranking/abstention; injection via `scan_for_injection` unit tests +
an endpoint that expects a block. **🔵 There is no Selenium/browser test of the
frontend, and no cross-service (AI↔Core over the network) integration test in the
suite** — the Core client is tested with `httpx.MockTransport`.

🗣️ **Say:** "282 offline, deterministic tests across every layer. Because the app is
wired from test settings, we swap in a fake LLM and in-memory stores with no
monkeypatching. The presentation tests prove auth (401) and tenant isolation (403)
against the real app via FastAPI's TestClient."

❓ *Medium:* How are external deps replaced? → via test `Settings` at the composition
root. *Hard:* What proves tenant isolation? → `test_ai_endpoints` cross-tenant test.
*Trick:* "Do tests call the real Anthropic API?" → No — the fake provider; fully
offline.

---

# §15 — Code-Quality Tools 🟡

| Tool | Job | Config |
|---|---|---|
| **Ruff** | fast linter (bugs, imports, style rules) | `pyproject.toml [tool.ruff]` |
| **Black** | auto-formatter (consistent layout) | `pyproject.toml` (line-length 100) |
| **mypy** | static type-checker (`--strict` on domain+application) | `pyproject.toml`/CI |
| **pytest** | test runner (+ coverage gate ~85%) | `pyproject.toml`, `tests/` |
| **import-linter** | enforces the 4 architecture contracts | `.importlinter` |
| **pre-commit** | runs these on `git commit` | `.pre-commit-config.yaml` |

**Difference in one line each:** *Black* makes it look the same; *Ruff* finds
likely mistakes; *mypy* checks types; *pytest* checks behavior; *import-linter*
checks the architecture. All run in CI (§19).

🗣️ **Say:** "Ruff lints, Black formats, mypy `--strict` type-checks the core layers,
pytest runs 282 tests with a coverage gate, and import-linter enforces the four
dependency contracts — all wired into pre-commit and CI."

❓ *Easy:* Black vs Ruff? → formatter vs linter. *Medium:* What does import-linter
add? → fails the build if a layer imports the wrong direction.

---

# §16 — Docker & Docker Compose 🔴 (very important — know this cold)

## Fundamentals (plain + analogy)
- **Image** = a frozen snapshot of an app + its dependencies (like a *recipe result*, a ready meal). **Container** = a running instance of an image (the meal being eaten). **Dockerfile** = the recipe. **Volume** = persistent storage that outlives a container (a fridge). **Network** = how containers talk. **Port mapping** (`8000:8000` = host:container) = which door on your machine reaches which door in the container. **Env vars** = settings passed in at run time. **Healthcheck** = Docker periodically asks "are you alive?"

## The AI-service `Dockerfile` — line by line (`ai-service/Dockerfile`)
Multi-stage, non-root, minimal.
```
FROM python:3.11-slim-bookworm AS builder     # stage 1: build deps in isolation
  ENV PYTHONDONTWRITEBYTECODE/UNBUFFERED/PIP_NO_CACHE  # clean, quiet, small
  RUN python -m venv /opt/venv                 # isolated virtualenv (cacheable layer)
  COPY requirements.txt ; pip install -r ...   # deps first → layer caches across code edits
  COPY pyproject/README/src ; pip install --no-deps .   # then install the app package
FROM python:3.11-slim-bookworm AS runtime     # stage 2: tiny final image (no build tools)
  useradd ciq (uid 1001)                       # NON-ROOT: defence-in-depth
  COPY --from=builder /opt/venv /opt/venv      # bring only the venv
  COPY corpus ./corpus ; prompts ; migrations  # assets loaded at startup
  USER ciq ; EXPOSE 8000                        # drop privileges; document the port
  HEALTHCHECK ... urlopen('http://127.0.0.1:8000/health')   # stdlib liveness probe
  CMD ["python","-m","complianceiq"]           # exec form → PID 1 gets SIGTERM (graceful stop)
```
**Why it's built this way:** multi-stage = small, no build tools in prod; deps-before-code = fast rebuilds; non-root + healthcheck + exec-form CMD = production hygiene.

## Two compose files (know the difference) 🔴
**(a) `ai-service/docker-compose.yml`** — the AI service *alone* for local dev:
`ai-service` (built from the Dockerfile, `8000:8000`, `env_file: .env`) + `postgres`
(`pgvector/pgvector:pg16`). Postgres is only *used* if `CIQ_VECTOR_STORE=pgvector`
(the app defaults to in-memory), so it's provisioned-but-optional here.

**(b) root `CIQ-FINAL/docker-compose.yml`** — the **integrated stack** (what you
demo). Services:
```
Docker Compose (root)
├── postgres        # the Core's database (pgvector image)
├── core-migrate    # runs `alembic upgrade head` once, then exits
├── core            # Core API on :8000 (signs RS256, serves /ai-contract + JWKS)
└── ai              # AI on :8100, wired to the Core (CIQ_CORE_CLIENT=http, RS256 JWK)
```
**How they communicate:** on the compose network, services reach each other by
**service name** — the AI calls the Core at `http://core:8000` (not `localhost`).
`localhost` inside a container means *that container*, not your laptop — this is the
#1 Docker networking gotcha. **Port mapping** (`8100:8000`) exposes the AI to your
laptop at `localhost:8100`. **Dependencies + healthchecks:** `ai` waits for `core`
to be *healthy*; `core` waits for `postgres` healthy and `core-migrate` completed.

**Start the whole platform locally (the answer to "how do I run it?"):**
```bash
python scripts/gen_integration_keys.py                 # 1. shared RS256 key (Core signs / AI verifies)
export JWT_PRIVATE_KEY="$(cat secrets/core-signing.pem)"   # 2. (PowerShell: $env:JWT_PRIVATE_KEY = Get-Content ... -Raw)
docker compose up --build                              # 3. build + start postgres→core→ai
# Core → http://localhost:8000   ·   AI console → http://localhost:8100
```

## Commands you must know
| Command | What it does / when |
|---|---|
| `docker compose up` | start all services (foreground) |
| `docker compose up --build` | rebuild images first (after code/Dockerfile changes) |
| `docker compose up -d` | start detached (background) |
| `docker compose ps` | list services + health/status |
| `docker compose logs` / `logs -f ai` | view logs / follow the AI service's logs live |
| `docker compose exec ai <cmd>` | run a command *inside* the running AI container (e.g. `exec ai python -c "..."`) |
| `docker compose down` | stop + remove containers/network (add `-v` to wipe volumes) |
| `docker compose config` | render the fully-resolved compose (debug env/interpolation) |

**Build-time vs runtime config:** the `Dockerfile` bakes code/deps at **build**;
`environment:`/`.env` inject settings at **run** — so you change config without
rebuilding. **Secrets:** the RS256 private key is passed via a shell env var (not
committed); the public JWK sits in `.env` (public, safe).

🗣️ **Say:** "The AI ships as a multi-stage, non-root image with a `/health`
healthcheck and `python -m complianceiq` as PID 1. To run the whole platform I use
the root `docker-compose.yml`: Postgres, a one-shot Core migration, the Core on
8000, and the AI on 8100, all on one network where the AI reaches the Core by
service name at `http://core:8000`. Generate the shared RS256 key, export the
private key, `docker compose up --build`."

❓ *Easy:* image vs container? *Medium:* Why does the AI use `http://core:8000` not
`localhost:8000`? → containers resolve each other by service name; `localhost` is the
container itself. *Hard:* Why multi-stage + non-root? → small image, no build tools
in prod, reduced blast radius. *Trick:* "Change an env var — rebuild the image?" →
No, env is runtime; just restart.

---

# §17 — PostgreSQL / Database 🟡

**Key truth:** the AI service is **stateless by default** — it uses **no database**
(in-memory vector + keyword stores). Postgres is **optional**, only when
`CIQ_VECTOR_STORE=pgvector`, and then it's the **pgvector** extension storing
embeddings. The AI **never** connects to the Core's database — it reads findings over
**HTTP** (the `CoreClient` port).

**When pgvector is on:** `infrastructure/knowledge/pgvector_store.py` (behind the
`VectorStore` port) talks to Postgres via a thin `SqlExecutor` seam
(`psycopg_executor.py`); schema in `migrations/0001_knowledge_pgvector.sql`
(applied out-of-band). Config: `CIQ_DATABASE_URL`, `CIQ_VECTOR_STORE`.

🗣️ **Say:** "The AI service is stateless and needs no DB by default — retrieval is
in-memory. You can switch to a pgvector Postgres backend via config, behind the same
`VectorStore` port. It never touches the Core's database; it reads findings over
HTTP."

❓ *Medium:* Does the AI use the Core's DB? → No — HTTP only. *Trick:* "Show me the AI
service's tables." → None by default; only the optional pgvector embedding table.

---

# §18 — Configuration & Environment Variables 🔴

**Real:** `infrastructure/config/settings.py` — a Pydantic-settings model, prefix
`CIQ_`, reads env or `.env`, validated once and **frozen**; secrets are `SecretStr`
(masked `repr`). Missing config fails fast at startup.

| Env var | Meaning | Secret? | If missing |
|---|---|---|---|
| `CIQ_ENVIRONMENT` | `local`/`production` (prod disables dev-login) | no | defaults `local` |
| `CIQ_CORE_CLIENT` | `stub` (offline) or `http` (real Core) | no | defaults `stub` (won't call Core) |
| `CIQ_CORE_API_BASE_URL` | the Core's URL | no | defaults `http://core-stub:9000` |
| `CIQ_JWT_PUBLIC_KEY` | the Core's public **JWK** → selects RS256 | no (public) | empty → **HS256 dev** verifier |
| `CIQ_JWT_ISSUER` / `CIQ_JWT_AUDIENCE` | must match the Core | no | default `complianceiq-core`/`complianceiq` |
| `CIQ_JWT_HS256_SECRET` | dev signing secret | **yes** | insecure default (dev only) |
| `CIQ_LLM_PRIMARY_PROVIDER` | `fake`/`anthropic`/`openai_compatible` | no | defaults `fake` (offline) |
| `CIQ_ANTHROPIC_API_KEY` | Claude key | **yes** | empty → can't use Anthropic |
| `CIQ_VECTOR_STORE` | `memory`/`pgvector` | no | defaults `memory` |
| `CIQ_DATABASE_URL` | Postgres URL (pgvector mode) | **yes** | only needed for pgvector |
| `CIQ_PORT` / `CIQ_HOST` | bind address | no | 8000 / 0.0.0.0 |

**Dev vs prod:** dev = `local` env, `fake` provider, in-memory, HS256 dev-login. Prod
= `production`, real provider + key, RS256 JWK from the Core, no dev-login. `.env` /
`.env.example` document these; the integrated stack sets them in the root compose.

🗣️ **Say:** "All config is `CIQ_*` env, validated once by a frozen Pydantic-settings
model with masked secrets. The important ones select the LLM provider, the Core
client (stub vs http), the vector store, and the JWT verification key — which is what
flips the AI from offline HS256 dev mode to RS256 talking to the real Core."

❓ *Medium:* What flips the AI to verify real Core tokens? → setting
`CIQ_JWT_PUBLIC_KEY` to the Core's JWK (auto-selects RS256). *Hard:* Why `SecretStr`?
→ masked repr so secrets don't leak into logs/tracebacks.

---

# §19 — CI/CD 🟡

**Real:** `.github/workflows/ci.yml` (GitHub Actions), on every push/PR:
```
git push → GitHub Actions "quality" job:
  install → Ruff (lint) → Black --check (format) → mypy --strict (domain+application)
  → lint-imports (4 architecture contracts) → pytest --cov (coverage gate) → upload coverage
```
"Green locally = green in CI" — it mirrors pre-commit. **🔵 NOT IMPLEMENTED in CI
yet:** Docker image build/publish, security scanning, and deployment stages
(the pipeline is quality-gates only today).

🗣️ **Say:** "CI runs Ruff, Black, mypy `--strict`, import-linter, and pytest with
coverage on every push. It's quality-gates only right now — image build, security
scanning, and deploy aren't wired yet."

❓ *Medium:* What runs in CI? → lint/format/types/architecture/tests. *Trick:* "CI
deploys to prod?" → No — not implemented; quality gates only.

---

# §20 — Debugging / Troubleshooting 🔴 (decision tree)

| Symptom | First check | Likely cause / fix |
|---|---|---|
| **Service won't start** | the startup logs | bad config (Pydantic validation fails fast) — read the error; a missing required secret |
| **Container exits immediately** | `docker compose logs ai` | crash on boot (config/import); healthcheck unrelated; fix the logged error |
| **`docker compose up` → "cannot connect to Docker daemon"** | is Docker Desktop running? | start Docker Desktop; Linux-containers mode |
| **API 401** | the `Authorization` header + token | missing/expired token, or wrong `iss`/`aud`/`alg`; in prod use a real RS256 token; ensure `CIQ_JWT_PUBLIC_KEY` set |
| **API 403** | token tenant vs finding tenant | acting cross-tenant (expected); use the matching tenant |
| **API 422** | the request body vs `schemas.py` | unknown/typo'd field or wrong type — the envelope `details` names it |
| **LLM request fails (502)** | gateway logs; `ProviderError` | provider down / retries exhausted; offline default is `fake`, so repeated 502 usually = restart mid-request |
| **RAG returns nothing / always abstains** | was the corpus seeded? the question | `_seed_corpus` didn't run, or the query is genuinely off-corpus (correct abstention) |
| **DB connection fails** | `CIQ_VECTOR_STORE`, `CIQ_DATABASE_URL` | only relevant in pgvector mode; default `memory` needs no DB |
| **Env var missing** | `settings.py`; a stray `.env` | defaults work offline; remove unintended overrides; required secrets fail loudly |
| **Port already in use (8000/8100)** | `docker compose ps` / what's on the port | change the host port mapping or stop the other process |
| **Container healthcheck fails** | `docker compose ps` (unhealthy) + `logs` | app not serving `/health` yet (raise `start_period`) or crashed |

**General method:** reproduce → read the error-envelope `code` (maps 1:1 to an
exception in `errors.py`) → open that exception's raise site → walk out to the router.
The `correlation_id` ties a response to its logs.

🗣️ **Say:** "I debug by the error envelope's `code`, which maps directly to a typed
exception; for containers I read `docker compose logs -f <svc>` and `ps` for health.
401 = token, 403 = tenant, 422 = body, 502 = provider, 503 = Core/DB."

---

# §21 — Code Walkthroughs 🔴 (each arrow = a real file/function)

**A. HTTP request → response (enrich):**
```
HTTP POST /api/v1/ai/enrich            presentation/routers/ai.py  enrich()
 → Depends(get_auth_context)           presentation/container.py → token_verifier.verify()  (infrastructure/auth/jwt_base.py)
 → _assert_tenant(body.findings, auth) domain/policies/tenant_isolation.py  (403 if mismatch)
 → agents.compliance_analyst.analyze   application/agents/compliance_analyst.py (BoundedAgent)
 → EnrichmentGraph.run                 application/graphs/enrichment.py  (retrieve→route→generate|abstain)
 → HybridRetriever.retrieve            application/knowledge/retrieval.py
 → AIGateway.generate                  application/gateway/ai_gateway.py → provider (infrastructure/providers/fake.py)
 → verify_citations                    domain/policies/grounding.py → sets citation_verified
 → EnrichedFinding (JSON)              domain/entities/finding.py
```

**B. Application startup:** `__main__.main` → `asgi.app = build_app()` →
`composition.build_container` → `create_app` → lifespan `_seed_corpus`. (§4)

**C. Authentication:** `get_auth_context` → `BaseJwtVerifier.verify` (split →
alg-pin → signature → temporal → iss/aud) → `AuthContext`. (§6)

**D. RAG query:** `HybridRetriever.retrieve` → semantic (`vector_store_memory`) +
lexical (`keyword_index_memory`) → `reciprocal_rank_fusion` (`fusion.py`) →
`reranker_lexical` → `mmr_select` → threshold → `context_assembly`. (§10)

**E. Remediation:** `routers/ai.py remediate()` → `RemediationEngineer.propose` →
`remediation.py` graph → `RemediationProposal` with `approved` forced `false` by a
validator (`domain/entities/remediation.py`).

**F. Error handling:** any `ComplianceIQError` bubbles to
`presentation/errors.py` handlers → `ErrorEnvelope` + status code. (§13)

**G. Docker startup:** `docker compose up` → build image (`Dockerfile`) → container
runs `python -m complianceiq` (PID 1) → healthcheck polls `/health` → compose marks
`ai` healthy → dependents proceed. (§16)

---

# §22 — Defense Wrap-up 🔴 (the three questions you WILL get)

**"Why did you build it this way?"**
"Clean Architecture with Ports & Adapters so the business core is testable in
isolation and vendors are swappable; a single AI Gateway so every model call is
uniformly rate-limited, budgeted, injection-scanned, cached, retried, and
cost-accounted; grounding with verified citations plus abstention so outputs are
auditable; and the whole thing runs offline via a fake provider so tests are
deterministic. The dependency rule is enforced by import-linter in CI, so the
architecture can't silently rot."

**"What would you improve?"** (honest, real gaps)
- Build the **Core→AI push** client (today only AI→Core pull exists).
- Add a **cross-service integration test** (real AI↔Core over HTTP) and a JWKS-fetch
  verifier so the AI can pull the Core's key automatically.
- Wire **Docker build + security scanning + deploy** into CI (quality-gates only now).
- Backend **report PDF export** and **corpus browsing** (frontend marks these future).
- Per-request DB session scoping if pgvector/DB usage grows.

**"What are the security risks?"** (and mitigations)
- Prompt injection via retrieved docs → scanned at the gateway + fenced + tool-output
  scanning (defence-in-depth, not absolute).
- Token forgery/downgrade → algorithm pinning, iss/aud/exp checks, RS256 in prod.
- Cross-tenant leakage → tenant from verified token, tenant-scoped cache keys,
  defense-in-depth re-check in `HttpCoreClient`.
- Secret exposure → `SecretStr`, private key never on the AI side, error envelope
  hides internals.
- Over-spend/abuse → per-tenant rate limit + budget in the gateway.

---

*Companion:* `COMPLIANCEIQ_AI_MASTERY_CHECKLIST.md` — track mastery per section, run
the final exam, and confirm you can defend the project. Other refs:
`ai-service/docs/ARCHITECTURE.md`, `RAG.md`, `AGENTS.md`, the ADRs, and
`ai-service/docs/study-guide/` (Field Guide PDF + one-page cheat sheet).
