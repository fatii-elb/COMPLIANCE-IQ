# Observability (Phase 8)

ComplianceIQ emits four kinds of operational signal: **structured logs**,
**correlation IDs**, **per-run traces**, and **metrics**. Together they let an
operator answer "is it healthy, how fast, how much is it costing, and what happened
to *this* request?" — without attaching a debugger.

## Structured logs

Logging is JSON (via `structlog`) in production and human-readable locally
(`CIQ_LOG_JSON`). Every log line carries the request's **correlation ID** (below),
and the AI gateway logs each model call with tenant, feature, model, token counts,
and cost (`ai_generate_ok`). Secrets and full customer payloads are never logged.

## Correlation IDs

The `CorrelationIdMiddleware` assigns each request an ID — reusing an inbound
`X-Correlation-ID` header if present, else generating one — binds it to every log
line for that request, echoes it in the `X-Correlation-ID` **response** header, and
includes it in every error envelope. This is the backbone of the audit trail (rule
7): a client-visible error carries an ID an operator can grep the logs for.

## Traces

Every LangGraph workflow run accumulates a **trace**: one `TraceEvent` per node
(`{node, status, duration_ms, detail}`), emitted through `traced_node`. A run is
therefore self-describing — you can see which nodes ran, in what order, how long
each took, and whether the graph abstained or generated.

## Metrics

An in-memory `MetricsSink` (behind the `MetricsSink` port) collects two families of
series, exposed in Prometheus text format at **`GET /metrics`** (operational and
unauthenticated, like the health probes — it carries only aggregates, never
per-tenant data):

| Series | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `http_requests_total` | counter | `method`, `route`, `status` | Requests served, by matched route + status |
| `http_request_duration_ms` | summary | `method`, `route` | Latency (`_count`/`_sum`/`_min`/`_max`) |
| `ai_gateway_calls_total` | gauge | — | Model calls made |
| `ai_gateway_cache_hits_total` | gauge | — | Responses served from cache |
| `ai_gateway_input_tokens_total` | gauge | — | Total input tokens |
| `ai_gateway_output_tokens_total` | gauge | — | Total output tokens |
| `ai_gateway_cost_usd_total` | gauge | — | Total spend (USD) |

The HTTP series come from `MetricsMiddleware` (it times each request against the
**matched route template**, so cardinality stays bounded). The `ai_gateway_*`
gauges come from the gateway's **usage ledger**, which also answers per-tenant spend
for budget enforcement (Phase 2). The `MetricsMiddleware` is best-effort: a metrics
failure can never break a request.

Example scrape:

```text
http_requests_total{method="POST",route="/api/v1/ai/enrich",status="200"} 12
http_request_duration_ms_count{method="POST",route="/api/v1/ai/enrich"} 12
http_request_duration_ms_sum{method="POST",route="/api/v1/ai/enrich"} 1843.2
ai_gateway_calls_total 12
ai_gateway_input_tokens_total 26188
ai_gateway_cost_usd_total 0.42
```

The port lets a real exporter (Prometheus client / OpenTelemetry) swap in behind
`MetricsSink` with no caller change.

## Answer-quality evaluation

Observability tells you the system is *running*; the **evaluation harnesses** tell
you it's *good*. Two exist, both offline (fake provider + bundled corpus), both
regression-tested:

- **Retrieval eval** (`application/knowledge/evaluation.py`) — recall@k,
  precision@k, MRR, hit-rate over a golden query set. Answers "did retrieval find the
  right sources?"
- **Grounding eval** (`application/evaluation/grounding_eval.py`) — grounded rate,
  abstention rate, citation precision/recall over a golden finding set. Answers "did
  the *answer* cite verified sources / abstain correctly?"

Run the grounding eval:

```bash
python -m scripts.evaluate_ai          # human-readable
python -m scripts.evaluate_ai --json   # machine-readable
```

Because grounding is the product's core guarantee, this harness makes it a
**measured, gate-able number** rather than a hope.

## Health & readiness

- `GET /health` — liveness (the process is up).
- `GET /health/ready` — readiness: every dependency probe (each provider + the
  vector store) is reachable; returns `503` if not, so orchestrators pull the
  instance from rotation.
- `GET /version` — name, semantic version, environment.
