# ComplianceIQ AI Service — Mastery Checklist

> Companion to **`COMPLIANCEIQ_AI_ZERO_TO_HERO.md`**. Each block references its
> guide section (§N). Work a section in the guide, then tick its boxes here.
> **Goal:** every 🔴 block at **Level 4** before you present.

## The 4 mastery levels (tick in order)
- **L1 — Recognition:** "I know what this is."
- **L2 — Understanding:** "I can explain it in my own words, and why ComplianceIQ uses it."
- **L3 — Implementation:** "I can find it in the repo and explain its runtime flow."
- **L4 — Defense:** "I can answer a hard question and troubleshoot it."

Priority: 🔴 MUST · 🟡 SHOULD · ⚪ NICE. **Don't treat boxes equally — 🔴 first.**

Progress: ___ / 22 sections at L4 · Exam score ___ /75 · Defense checklist ___ /18

---

## §1 — Big Picture 🔴 (Guide §1)
- [ ] L1: I know ComplianceIQ = a compliance platform; the AI service reasons over findings.
- [ ] L2: I can explain the problem it solves, who uses it, and AI-is/AI-is-NOT responsible.
- [ ] L3: I can state the implemented flow (AI **pulls** findings from the Core) and name the 4 non-negotiable rules.
- [ ] L4: I can answer "where does the AI store findings?" (it doesn't) and "which integration direction exists?" (AI→Core pull; Core→AI push NOT implemented).

## §2 — Repository Structure 🟡 (Guide §2)
- [ ] L1: I recognize `ai-service/`, `core-service/`, root compose.
- [ ] L2: I can explain the four `src/complianceiq` layers + composition root.
- [ ] L3: I can say what `composition.py`, `asgi.py`, `__main__.py`, `routers/ai.py`, `settings.py` each do.
- [ ] L4: I can say where I'd add a new endpoint (router + agent).

## §3 — Architecture 🔴 (Guide §3)
- [ ] L1: I can name the pattern (Clean Architecture + Ports & Adapters + composition root).
- [ ] L2: I can explain the inward dependency rule, ports vs adapters, and DI in my own words.
- [ ] L3: I can point to `domain/ports/llm.py` (port), `infrastructure/providers/*` (adapters), `composition.py` (wiring), `presentation/container.py` (Container Protocol).
- [ ] L4: I can name the **4 import-linter contracts** and explain how the architecture is *enforced* in CI.
- [ ] Task: I can explain "why a port instead of importing the adapter?" without notes.

## §4 — Startup & Execution 🔴 (Guide §4)
- [ ] L1: I know `python -m complianceiq` starts uvicorn.
- [ ] L2: I can explain what `build_app`/`build_container` do.
- [ ] L3: I can trace `__main__ → asgi → composition → create_app → lifespan _seed_corpus`.
- [ ] L4: I can explain the RS256/HS256 verifier auto-selection at startup.
- [ ] Task: I can answer "what happens from start until it's ready for a request?" in ~30s.

## §5 — FastAPI / HTTP API 🔴 (Guide §5)
- [ ] L1: I know HTTP methods, status codes, JSON, and what Swagger is.
- [ ] L2: I can explain routers, request/response models, and 422 validation.
- [ ] L3: I can list the endpoint map and trace `enrich()` internally.
- [ ] L4: I can explain why responses are domain contracts (no DTO drift).
- [ ] Task: I can open `/docs` (Swagger) and call an endpoint.

## §6 — Authentication & Security 🔴 (Guide §6)
- [ ] L1: I know JWT = signed token; the AI **verifies**, the Core **issues**.
- [ ] L2: I can explain auth vs authz and 401 vs 403.
- [ ] L3: I can walk the verify pipeline in `jwt_base.py` and point to `get_auth_context` + `assert_same_tenant`.
- [ ] L4: I can explain how the code stops **`alg:none`**, **RS256→HS256 confusion**, forged/expired/missing tokens, wrong iss/aud, and cross-tenant access.
- [ ] Task: I can explain, with a diagram, an authenticated request end to end.

## §7 — Pydantic vs mypy 🟡 (Guide §7)
- [ ] L1: I know one is runtime, one is static.
- [ ] L2: I can explain when each runs and what each catches.
- [ ] L3: I can point to `domain/_base.py` (`FrozenModel`, `extra="forbid"`) and `settings.py`.
- [ ] L4: I can answer "which one rejects a bad request body?" (Pydantic → 422) and "does mypy validate requests?" (no).

## §8 — LLM Provider Architecture 🔴 (Guide §8)
- [ ] L1: I know the app talks to an interface, not Anthropic directly.
- [ ] L2: I can distinguish Domain / Port / Adapter / Gateway / actual provider.
- [ ] L3: I can point to `domain/ports/llm.py`, `infrastructure/providers/*`, `ai_gateway.py`, `routing.py`.
- [ ] L4: I can answer "how do you change LLM providers without rewriting the app?" and explain retry/circuit-breaker/cache location.
- [ ] Task: I can explain the gateway's pre-flight order (rate-limit→budget→injection→cache→route).

## §9 — Prompts & Prompt-Injection 🔴 (Guide §9)
- [ ] L1: I know what a prompt template and prompt injection are.
- [ ] L2: I can explain direct vs indirect injection and why RAG is vulnerable.
- [ ] L3: I can point to `prompts/*.prompt`, `prompt_safety.py scan_for_injection`, and the gateway's `_scan_untrusted`.
- [ ] L4: I can explain why scanning at the gateway covers every feature, and that it's defence-in-depth (not absolute).

## §10 — RAG / Knowledge Base 🔴 (Guide §10)
- [ ] L1: I can state the RAG loop (retrieve → context → LLM → grounded answer).
- [ ] L2: I can explain embeddings, similarity search, chunks, grounding, abstention.
- [ ] L3: I can name the 6 pipeline steps and point to `retrieval.py`, `fusion.py`, `context_assembly.py`, `corpus/frameworks/*`.
- [ ] L4: I can explain hallucination prevention (`verify_citations` + abstain) and correctly say **it's NOT ChromaDB** (in-memory / optional pgvector).
- [ ] Task: I can explain why retrieval is **hybrid** (semantic + lexical).

## §11 — Compliance Domain 🟡 (Guide §11)
- [ ] L1: I know framework / control / finding / evidence / remediation.
- [ ] L2: I can name the 5 corpus frameworks (ISO 27001, NIST CSF, SOC 2, Loi 05-20, DNSSI).
- [ ] L3: I can narrate a finding → grounded EnrichedFinding transformation.
- [ ] L4: I can answer "do you store the full ISO standard?" (no — identifiers + summaries, copyright).

## §12 — AI Features 🔴 (Guide §12)
- [ ] L1: I can name the 7 features.
- [ ] L2: I can map each feature to its endpoint and agent/graph.
- [ ] L3: I can trace the generic feature flow (auth→tenant→agent→graph→gateway→contract).
- [ ] L4: I can explain `approved=false` (rule 2) and deterministic financial numbers.

## §13 — Error Handling 🟡 (Guide §13)
- [ ] L1: I know errors map to one envelope.
- [ ] L2: I can explain typed exceptions vs HTTP mapping.
- [ ] L3: I can point to `domain/exceptions.py` and `presentation/errors.py` and recite the code→status map.
- [ ] L4: I can explain why "RAG found nothing" is a 200 abstention, not a 500.

## §14 — Testing 🔴 (Guide §14)
- [ ] L1: I know there are 282 offline tests.
- [ ] L2: I can explain unit vs integration and how fakes are injected via test `Settings`.
- [ ] L3: I can name `test_ai_endpoints.py`, `test_ai_gateway.py`, `test_core_client.py`, `test_rs256_verifier.py`.
- [ ] L4: I can name the test that proves tenant isolation and explain why no real Anthropic call happens.
- [ ] Task: I can run `pytest -q` and read a failing test.

## §15 — Code-Quality Tools 🟡 (Guide §15)
- [ ] L1: I recognize Ruff, Black, mypy, pytest, import-linter.
- [ ] L2: I can give the one-line difference between Black, Ruff, mypy, pytest.
- [ ] L3: I can say where each is configured (`pyproject.toml`, `.importlinter`).
- [ ] L4: I can explain what import-linter adds over the others.

## §16 — Docker & Compose 🔴 (Guide §16)
- [ ] L1: I know image/container/Dockerfile/volume/port-mapping/healthcheck.
- [ ] L2: I can explain the multi-stage, non-root Dockerfile and why.
- [ ] L3: I can describe **both** compose files and the root architecture (postgres/core-migrate/core/ai).
- [ ] L4: I can explain container-to-container networking (`http://core:8000`) vs `localhost`, and build-time vs runtime config.
- [ ] Task: I can **start the full platform** (`gen_integration_keys` → export key → `docker compose up --build`).
- [ ] Task: I can `docker compose ps`, `logs -f ai`, `exec ai ...`, and `down`.
- [ ] Task: I can identify **why a container failed** from its logs.

## §17 — PostgreSQL 🟡 (Guide §17)
- [ ] L1: I know the AI service is stateless by default (no DB).
- [ ] L2: I can explain when Postgres/pgvector is used (`CIQ_VECTOR_STORE=pgvector`).
- [ ] L3: I can point to `pgvector_store.py`, `psycopg_executor.py`, `migrations/`.
- [ ] L4: I can answer "does the AI use the Core's DB?" (no — HTTP only).

## §18 — Configuration 🔴 (Guide §18)
- [ ] L1: I know config is `CIQ_*` env via `settings.py`.
- [ ] L2: I can explain dev vs prod config and `SecretStr`.
- [ ] L3: I can explain each key var (CORE_CLIENT, JWT_PUBLIC_KEY, LLM_PRIMARY_PROVIDER, VECTOR_STORE).
- [ ] L4: I can say **what flips the AI to verify real Core tokens** (set `CIQ_JWT_PUBLIC_KEY` → RS256).

## §19 — CI/CD 🟡 (Guide §19)
- [ ] L1: I know CI runs on push via GitHub Actions.
- [ ] L2: I can list the CI stages (lint/format/types/architecture/tests).
- [ ] L3: I can point to `.github/workflows/ci.yml`.
- [ ] L4: I can honestly say image build / security scan / deploy are **NOT** wired yet.

## §20 — Debugging 🔴 (Guide §20)
- [ ] L1: I know 401/403/422/502/503 meanings.
- [ ] L2: I can use the decision tree for the common failures.
- [ ] L3: I can map an error `code` to its exception in `errors.py`.
- [ ] L4: I can diagnose: won't start, container exits, 401/403/422, LLM fail, RAG empty, DB fail, port in use, unhealthy.

## §21 — Code Walkthroughs 🔴 (Guide §21)
- [ ] L3: I can name the file/function at **every arrow** of the enrich request flow.
- [ ] L4: I can do the same for startup, auth, RAG, remediation, error handling, and Docker startup — from memory.

## §22 — Defense Wrap-up 🔴 (Guide §22)
- [ ] L4: I can answer "why did you build it this way?" in ~45s.
- [ ] L4: I can answer "what would you improve?" with the real gaps.
- [ ] L4: I can answer "what are the security risks?" with mitigations.

---

# 🎓 Final Exam (test yourself — answers at the very end)

Score: A–F = 1 pt each (60), G = 2 pts each (10), H = 0.5 pt each (5). Total **/75**.
Don't scroll to the Answer Key until you've written your answers.

## Part A — Architecture (10)
1. Name the four layers and the direction dependencies point.
2. What is a *port* and what is an *adapter*? Give one of each from the repo.
3. What does `composition.py` do, and what is it uniquely allowed to import?
4. Name the four import-linter contracts.
5. How can presentation reach services without importing infrastructure?
6. Why must the domain not import infrastructure?
7. What is the composition root's role during tests?
8. Where is dependency injection actually assembled?
9. Which layer holds `LLMProvider`, and which holds `AnthropicProvider`?
10. How is the architecture *enforced* rather than just documented?

## Part B — FastAPI / API (10)
1. Which endpoints require no auth?
2. What returns a 422 and which component produces it?
3. What are the AI endpoints' response bodies (DTOs or domain models)?
4. Trace `enrich()` internally in three steps.
5. Where is Swagger, and what generates it?
6. What's the difference between `/ai/enrich` and `/ai/enrich/by-ids`?
7. Which endpoint can *abstain*, and what does that look like?
8. What HTTP method do all AI capabilities use, and why?
9. What is the single error response shape?
10. Which endpoint exposes Prometheus metrics?

## Part C — Authentication / Security (10)
1. Does the AI issue or only verify tokens? Who issues?
2. 401 vs 403 in this system.
3. Walk the JWT verify pipeline (5 steps).
4. How is the `alg:none` attack prevented?
5. How is RS256→HS256 confusion prevented?
6. What claims must be present, and what iss/aud are required?
7. Where does the tenant come from, and why never from a param?
8. Name two places tenant isolation is enforced.
9. HS256 vs RS256 — why each, in which environment?
10. Is prompt injection an auth concern? Where is it handled?

## Part D — AI / LLM / RAG (10)
1. What are the five words: Domain / Port / Adapter / Gateway / provider — one line each here.
2. List the gateway's pre-flight checks in order.
3. What are the six RAG pipeline steps?
4. Why hybrid retrieval (semantic + lexical)?
5. What triggers abstention?
6. Who sets `citation_verified` — the model or policy code? Which file?
7. Which vector store does the AI use? (careful)
8. What does a bounded agent enforce (name three of five)?
9. Why are financial figures deterministic?
10. Direct vs indirect prompt injection — which threatens RAG most?

## Part E — Docker (10)
1. Image vs container.
2. What does `8100:8000` mean?
3. Why is the Dockerfile multi-stage and non-root?
4. Name the four services in the root compose.
5. How does the AI reach the Core inside compose — what URL?
6. Why not `http://localhost:8000` from inside the AI container?
7. What does `core-migrate` do and when does it exit?
8. Which command follows the AI's logs live?
9. Build-time vs runtime configuration — give an example of each.
10. What are the exact steps to start the whole platform locally?

## Part F — Testing / DevOps (10)
1. How many tests, and are they online or offline?
2. How are external dependencies replaced in tests (no monkeypatching)?
3. Name the test that proves cross-tenant blocking.
4. What does import-linter test?
5. One-line each: Black, Ruff, mypy, pytest.
6. What runs in CI, in order?
7. What is *not* implemented in CI yet?
8. Where is mypy `--strict` applied?
9. What's the coverage gate roughly?
10. What tool enforces the layer boundaries and where is it configured?

## Part G — Code tracing (2 pts each — name the file/function at each step)
1. A user clicks **Explain** in the console → trace to the JSON response.
2. `python -m complianceiq` → "ready for requests."
3. A Bearer token arrives → an `AuthContext` is produced.
4. A copilot question with no relevant corpus → the response.
5. `docker compose up` → the `ai` service is marked healthy.

## Part H — Troubleshooting (0.5 pt each — cause + first action)
1. API returns 401 on every call.
2. API returns 403 for a valid token.
3. API returns 422 on a POST.
4. `docker compose up` → "cannot connect to the Docker daemon."
5. The `ai` container exits immediately after start.
6. Every copilot answer abstains.
7. An LLM call returns 502.
8. "Port 8000 already in use."
9. The AI won't verify a real Core token (401 with a valid-looking token).
10. A container shows `unhealthy` in `docker compose ps`.

---

# ✅ Final "Can I defend this project?" checklist (18)
Tick only what you can do **without notes**:
- [ ] Explain the entire architecture from memory.
- [ ] Explain why the AI service exists (and what it does NOT do).
- [ ] Trace an HTTP request through the code, arrow by arrow.
- [ ] Explain authentication and the JWT verify pipeline.
- [ ] Explain the `alg:none` and RS256→HS256 defenses.
- [ ] Explain RAG end to end (and correctly say it's not ChromaDB).
- [ ] Explain prompt injection and the gateway defense.
- [ ] Explain the LLM provider abstraction (change vendors without rewriting).
- [ ] Explain Docker (image/container/healthcheck/non-root).
- [ ] Explain the Docker Compose architecture and container networking.
- [ ] Start the full platform and show it running.
- [ ] Troubleshoot a failed container from its logs.
- [ ] Explain the database story (stateless by default; optional pgvector; never the Core's DB).
- [ ] Explain the tests and how fakes are injected.
- [ ] Explain the CI pipeline (and what's not wired yet).
- [ ] Defend the architectural decisions ("why this way?").
- [ ] Answer "what would you improve?" honestly.
- [ ] Answer "what are the security risks?" with mitigations.

---

# 🔑 Answer Key (don't peek until you've tried)

**Part A:** 1) domain, application, infrastructure, presentation; deps point **inward**. 2) port = interface in `domain/ports` (e.g. `LLMProvider`); adapter = impl in `infrastructure` (e.g. `AnthropicProvider`). 3) wires all concretes into the app; only file allowed to import **both** infrastructure and presentation. 4) app→domain only · domain imports no frameworks · application imports no outer layers · presentation ⊥ infrastructure. 5) via the structural `Container` Protocol in `presentation/container.py` (no import edge). 6) so business rules are testable with no mocks/network/DB and adapters are swappable. 7) tests build the same graph with fakes by passing test `Settings`. 8) `composition.py`. 9) port in **domain**, adapter in **infrastructure**. 10) import-linter runs the 4 contracts in CI; a violation fails the build.

**Part B:** 1) `/health`, `/health/ready`, `/version`, `/metrics` (and LOCAL `/auth/dev-token`). 2) invalid body → **422**, produced by **Pydantic** (`extra="forbid"`/types). 3) **domain models** (e.g. `EnrichedFinding`), not separate DTOs. 4) `get_auth_context` (verify JWT) → `_assert_tenant` (403 if mismatch) → `agents.compliance_analyst.analyze`. 5) `/docs`, generated from FastAPI/OpenAPI. 6) `enrich` takes finding bodies; `enrich/by-ids` takes ids and **pulls** them from the Core. 7) `/ai/ask` → `CopilotAnswer` with `abstained=true`. 8) **POST** — they act/compute, not just read. 9) `{error:{code,message,correlation_id,details}}`. 10) `/metrics`.

**Part C:** 1) verify only; the **Core** issues. 2) 401 = bad/missing token; 403 = valid token, wrong tenant. 3) split → algorithm-pin → signature → temporal(exp/nbf) → iss/aud → `AuthContext`. 4) algorithm pinned; `none` rejected. 5) verifier accepts only its configured algorithm/family. 6) `sub`, `tenant_id`, `roles`, `exp`; iss=`complianceiq-core`, aud=`complianceiq`. 7) from the **verified token**; a param could be forged → cross-tenant read. 8) `assert_same_tenant` in `routers/ai.py`; tenant-scoped cache keys; plus `HttpCoreClient` re-check. 9) HS256 (shared secret) local dev; RS256 (private key only in Core) prod. 10) yes; at the **gateway** (`prompt_safety.scan_for_injection`).

**Part D:** 1) Domain=the vocabulary + the port; Port=`LLMProvider` interface; Adapter=vendor impl; Gateway=one policy choke point; provider=Anthropic/OpenAI/fake. 2) rate-limit → budget → injection scan (→ then cache → route). 3) semantic + lexical → RRF → rerank → MMR → threshold → context assembly. 4) semantic catches meaning, lexical catches exact control IDs. 5) the score threshold filtering everything out. 6) **policy code** — `domain/policies/grounding.py verify_citations`. 7) **in-memory** by default (optional pgvector) — **not ChromaDB**. 8) allow-list, iteration budget, wall-clock budget, loop detection, tool-output injection scan (any 3). 9) audit-defensible; the model can't invent figures (deterministic policy computes them). 10) **indirect** (poisoned retrieved documents).

**Part E:** 1) image=frozen snapshot; container=running instance. 2) host **8100** → container **8000**. 3) small image / no build tools in prod / reduced blast radius. 4) postgres, core-migrate, core, ai. 5) `http://core:8000` (service name). 6) `localhost` inside a container is that container, not the Core/host. 7) runs `alembic upgrade head` once, then exits. 8) `docker compose logs -f ai`. 9) build = Dockerfile bakes code/deps; runtime = `environment:`/`.env` (e.g. change a var, restart, no rebuild). 10) `gen_integration_keys.py` → export `JWT_PRIVATE_KEY` → `docker compose up --build`.

**Part F:** 1) **282**, offline/deterministic. 2) app built from test `Settings` at the composition root → fake provider + in-memory stores. 3) `test_cross_tenant_finding_is_blocked` (in `test_ai_endpoints.py`). 4) that layers only import inward (the 4 contracts). 5) Black=format, Ruff=lint, mypy=types, pytest=behavior. 6) install → ruff → black --check → mypy --strict → lint-imports → pytest --cov. 7) Docker build/publish, security scanning, deploy. 8) domain + application. 9) ~85%. 10) import-linter, `.importlinter`.

**Part G:** 1) `routers/ai.py enrich()` → `get_auth_context`(`jwt_base`) → `_assert_tenant`(`tenant_isolation`) → `compliance_analyst.analyze` → `EnrichmentGraph`(`graphs/enrichment.py`) → `HybridRetriever`(`retrieval.py`) → `AIGateway.generate`(`ai_gateway.py`) → `verify_citations`(`grounding.py`) → `EnrichedFinding` JSON. 2) `__main__.main` → `asgi.app=build_app()` → `composition.build_container` → `create_app` → lifespan `_seed_corpus`. 3) `get_auth_context` → `BaseJwtVerifier.verify` (split→alg→sig→temporal→iss/aud) → `AuthContext`. 4) `routers/ai.py ask()` → CopilotGraph → retrieve returns nothing → route to **abstain** node → `CopilotAnswer(abstained=true)`. 5) `docker compose up` → build `Dockerfile` → container runs `python -m complianceiq` → HEALTHCHECK polls `/health` → healthy → dependents start.

**Part H:** 1) missing/expired/invalid token or wrong iss/aud/alg → check the header + `CIQ_JWT_PUBLIC_KEY`. 2) cross-tenant (expected) → use the matching tenant. 3) bad body field/type → read envelope `details`. 4) Docker Desktop not running → start it. 5) crash on boot (config/import) → `docker compose logs ai`. 6) corpus not seeded or off-corpus question → check `_seed_corpus`/question. 7) provider failed/retries exhausted → gateway logs; offline default is fake so usually a restart mid-request. 8) another process on 8000 → change mapping/stop it. 9) AI in HS256 mode → set `CIQ_JWT_PUBLIC_KEY` to the Core's JWK (RS256). 10) app not serving `/health` yet or crashed → `logs` + raise `start_period`.

---
*Guide: `COMPLIANCEIQ_AI_ZERO_TO_HERO.md`. When every 🔴 block is at L4, the exam ≥ 65/75, and the 18-item defense checklist is fully ticked — you can defend this project.*
