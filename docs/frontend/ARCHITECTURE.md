# ComplianceIQ Frontend — Architecture

This document describes the ComplianceIQ web frontend: how it is built, how it
talks to the backend, and exactly what backend capability each screen consumes.
It is written to be honest about the boundary between what is **implemented** and
what is **future integration** — nothing here pretends functionality the backend
does not provide.

---

## 1. What this frontend is

A **single-page application (SPA)** that gives the ComplianceIQ AI service a
professional, enterprise GRC console. It is intentionally **build-tool-free**:
no npm, no bundler, no framework runtime. It is plain, modern **ES modules +
CSS**, served as static files by the existing FastAPI app at the **same origin**
as the API — so there is no CORS to configure and no second server to run.

> **Why no React/Vite?** The top requirement was a working product a
> non-developer client can run and test. Serving static ES modules from the
> existing backend means "start the backend, open one URL" — nothing to install
> or compile. The code is still structured like a real app (services, pages,
> router, state) so it could be ported to a framework later; see §11.

### Technology
| Concern | Choice |
|--------|--------|
| Language | Vanilla JavaScript (ES2022 modules) |
| Styling | Hand-written CSS design system (CSS custom properties, dark + light) |
| Charts | Inline SVG (no chart library) |
| Routing | Hash-based client router (`#/findings/:id`) |
| State | A small in-memory store module (no Redux/etc.) |
| Serving | FastAPI `StaticFiles` mount at `/` (same origin) |
| Auth | JWT bearer, verified server-side (HS256 dev / RS256 prod) |

---

## 2. Folder structure

```
frontend/
├── index.html                  App shell + boot loader
└── assets/
    ├── css/
    │   └── styles.css          The entire design system (tokens → components)
    └── js/
        ├── config.js           API base + enum/label/colour constants
        ├── icons.js            Inline SVG icon set
        ├── api.js              ★ The HTTP service layer (the only place fetch() lives)
        ├── auth.js             Session: token store, JWT decode, sign-in/out
        ├── store.js            In-memory findings cache + AI-result memoisation + metrics
        ├── charts.js           SVG donut / bar charts
        ├── ui.js               Rendering helpers: badges, states, toasts, modal, markdown-lite
        ├── router.js           Hash router
        ├── app.js              ★ Bootstrap + the authenticated shell (sidebar/topbar/routing)
        └── pages/
            ├── login.js        Authentication view
            ├── dashboard.js    Executive overview
            ├── findings.js     Findings table (search / filter / sort)
            ├── finding.js      Finding detail + 4 AI actions
            ├── copilot.js      Grounded chat
            ├── risk.js         Risk analytics + correlate + financial
            ├── reports.js      Enrich → report draft + export
            ├── frameworks.js   Framework coverage + control mapping
            ├── knowledge.js    Grounded corpus lookup
            └── settings.js     Session / connection / theme / sign-out
```

**Layering rule (mirrors the backend's Clean Architecture):** UI code in
`pages/*` never calls `fetch` directly — it calls typed functions in `api.js`.
`api.js` is the single choke point for HTTP, auth headers, timeouts, and error
normalisation. This is the frontend's version of the backend's "one gateway."

---

## 3. Data flow

```
 pages/*.js        (render + user events)
     │  calls typed functions
     ▼
 store.js          (cache findings once; memoise AI results per finding)
     │
     ▼
 api.js            (attach Bearer token, timeout, normalise errors)  ◄── auth.js sets the token
     │  fetch()  (same origin)
     ▼
 FastAPI  ──►  presentation routers  ──►  application (agents / gateway)  ──►  domain
```

A typical request (open a finding and explain it):

1. `finding.js` calls `store.findFinding(id)` (cache) or `api.getFinding(id)`.
2. User clicks **Explain** → `finding.js` calls `api.aiEnrich([finding])`.
3. `api.js` adds `Authorization: Bearer <jwt>`, POSTs `/api/v1/ai/enrich`, and
   either returns the parsed `EnrichedFinding[]` or throws a normalised `ApiError`.
4. `finding.js` renders the explanation with `ui.mdLite`, lists citations, and
   shows the **Grounded & Verified** badge from `citation_verified`.
5. The result is memoised in `store` so re-opening doesn't re-spend a model call.

---

## 4. The API service layer (`api.js`)

Every backend call has a named function. Endpoints actually consumed:

| Function | Method + path | Backend status |
|----------|---------------|----------------|
| `getHealth` | `GET /health` | **IMPLEMENTED** |
| `getVersion` | `GET /version` | **IMPLEMENTED** |
| `getReadiness` | `GET /health/ready` | **IMPLEMENTED** |
| `mintDevToken` | `POST /api/v1/auth/dev-token` | **IMPLEMENTED (LOCAL/dev only)** |
| `listFindings` | `GET /api/v1/findings` | **IMPLEMENTED** (added; wraps Core `list_findings`) |
| `getFinding` | `GET /api/v1/findings/{id}` | **IMPLEMENTED** (added; wraps Core `get_finding`) |
| `aiEnrich` | `POST /api/v1/ai/enrich` | **IMPLEMENTED** |
| `aiEnrichByIds` | `POST /api/v1/ai/enrich/by-ids` | **IMPLEMENTED** |
| `aiAsk` | `POST /api/v1/ai/ask` | **IMPLEMENTED** |
| `aiRemediate` | `POST /api/v1/ai/remediate` | **IMPLEMENTED** |
| `aiCorrelate` | `POST /api/v1/ai/correlate` | **IMPLEMENTED** |
| `aiMap` | `POST /api/v1/ai/map` | **IMPLEMENTED** |
| `aiFinancial` | `POST /api/v1/ai/financial` | **IMPLEMENTED** |
| `aiReport` | `POST /api/v1/ai/report` | **IMPLEMENTED** |

### Error handling
`api.js` converts every failure into an `ApiError` with a `kind` and a
client-safe message. HTTP status → kind → message:

| Status | kind | Message shown to the user |
|--------|------|---------------------------|
| network fail | `network` | "ComplianceIQ can't reach the backend service…" |
| abort/timeout | `timeout` | "The request took too long…" |
| 401 | `auth` | "Your session has expired or is invalid…" |
| 403 | `forbidden` | "You don't have access to this resource…" |
| 404 | `notfound` | "We couldn't find what you were looking for." |
| 400/422 | `validation` | "The request was rejected as invalid…" |
| 429 | `ratelimit` | "You've hit the rate limit for this tenant…" |
| 5xx | `server` | "ComplianceIQ hit an unexpected error…" |

The backend's error envelope (`{error:{code,message,correlation_id,details}}`) is
parsed; the `correlation_id` is surfaced in error states so a client can quote it
to support. Raw stack traces are never shown.

### Environment configuration
The API base is `""` (same origin) by default. To point a separately-served
frontend at a remote backend, set `window.CIQ_API_BASE` before `app.js` loads
(that backend must then enable CORS — the bundled same-origin setup needs none).

---

## 5. Authentication & session (`auth.js`)

The Core Service issues JWTs in production; **this AI service only verifies
them**. The frontend therefore has two ways to obtain a token:

1. **Developer sign-in** (default, local): posts to `POST /api/v1/auth/dev-token`,
   which mints a short-lived HS256 token. This endpoint is **only mounted in
   non-production environments** and refuses to run in production. It never
   weakens the real auth — the token is still verified server-side on every call.
2. **Paste a token**: the production path — paste a real Core-issued JWT (or one
   from `python -m scripts.mint_dev_token`).

`auth.js`:
- stores the token + decoded claims (`sub`, `tenant_id`, `roles`, `exp`) in
  `localStorage` (key `ciq.session.v1`),
- restores the session on reload (and drops it if expired),
- exposes `isAuthenticated()` used by the router as a **route guard** — every
  in-shell route bounces to the login view if the session is missing/expired,
- `app.js` runs an expiry watcher that signs the user out when the token lapses.

The token is attached to requests only through `api.setAuthToken()` — components
never see or forward it (except `settings.js`, which shows a masked preview).

---

## 6. Routing (`router.js` + `app.js`)

A hash router maps patterns to page modules:

| Route | Page | Purpose |
|-------|------|---------|
| `#/` | dashboard | Executive overview |
| `#/findings` | findings | Findings table |
| `#/findings/:id` | finding | Finding detail + AI |
| `#/frameworks` | frameworks | Coverage + control mapping |
| `#/copilot` | copilot | Grounded chat |
| `#/risk` | risk | Risk analytics + correlate/financial |
| `#/reports` | reports | Report generation |
| `#/knowledge` | knowledge | Grounded corpus lookup |
| `#/settings` | settings | Session / connection / theme |

`app.js` owns the **shell** (sidebar, topbar, breadcrumb, user menu, backend
status pill, mobile drawer) and renders each page into `#view`. Unauthenticated
users never see the shell — they get the full-screen login view.

Each page module exports `render(mountEl, ctx)` where `ctx` provides
`{ params, query, navigate, setCrumb, setNavBadge }`.

---

## 7. State (`store.js`)

Deliberately tiny — one module, no framework:
- **`loadFindings()`** fetches `GET /api/v1/findings` once and caches for 60s, so
  the dashboard, findings table, risk, reports, and frameworks pages share a
  single fetch.
- **AI result memoisation** keyed by `kind:findingId`, so re-opening a finding
  re-shows the explanation/mapping/etc. without re-spending a model call.
- **`computeMetrics()`** derives the dashboard/risk aggregates (score, severity
  counts, framework coverage, domain distribution) **client-side** — see §9.

---

## 8. Styling (`styles.css`)

A single token-driven design system:
- **Tokens** — brand, semantic severity colours (critical/high/medium/low),
  radii, shadows, typography, layout dimensions, all as CSS custom properties.
- **Theming** — dark by default; a full **light** palette under
  `[data-theme="light"]`. The choice persists in `localStorage` (`ciq.theme`) and
  is applied at boot before first paint.
- **Components** — cards, stat tiles, buttons, inputs, badges/chips, data tables,
  meters/bars, empty/loading/error states, skeletons, toasts, a modal, the chat
  surface, and the login split-screen.
- **Responsive** — desktop-first; the sidebar collapses to a drawer under 960px
  and grids reflow to single-column on small screens. A print stylesheet makes
  reports printable.

All severity/risk colours are **consistent everywhere** (badge, donut, bar,
legend) so the visual language is unambiguous.

---

## 9. Honest boundaries — what is real vs. computed vs. absent

| Capability | Status | Notes |
|-----------|--------|-------|
| JWT auth (verify) | **IMPLEMENTED** | HS256 (dev) / RS256 (prod), same `TokenVerifier` port |
| Dev sign-in endpoint | **IMPLEMENTED (dev only)** | `POST /api/v1/auth/dev-token`, LOCAL/non-prod only |
| Findings list + detail | **IMPLEMENTED** | New read endpoints wrapping the existing Core client; offline they read the seeded stub |
| Findings write/delete | **NOT IMPLEMENTED** | The Core Service owns scanning & writes; this service is a read-only consumer by design |
| Enrich / Ask / Remediate / Correlate / Map / Financial / Report | **IMPLEMENTED** | The 8 real AI endpoints |
| Dashboard & risk aggregates (score, counts, coverage) | **PARTIALLY IMPLEMENTED** | Computed **client-side** from the findings list — the backend exposes no aggregate endpoint. The compliance "score" is a transparent, weighted client-side summary, not a certification figure |
| Report draft generation | **IMPLEMENTED** | `POST /api/v1/ai/report` over enriched findings |
| Report PDF / download / storage | **NOT IMPLEMENTED** | Backend has no PDF renderer; the client offers Markdown export + browser print as an honest interim |
| Knowledge-base document browsing | **NOT IMPLEMENTED** | No corpus-browse endpoint; the page offers grounded lookup via `/ai/ask` (same RAG pipeline) instead |
| Conversation history persistence | **PARTIALLY IMPLEMENTED** | Copilot history is client-side for the session only; not stored server-side |
| Metrics / health | **IMPLEMENTED** | `/health`, `/health/ready`, `/version`, `/metrics` |

The UI **labels** these states in-product (e.g. the Knowledge Base and Reports
pages show `Not implemented` / `Future` tags where relevant).

---

## 10. Backend changes made for this frontend

To integrate honestly, a small, additive set of backend changes were made (all
covered by the existing 282-test suite, which still passes):

1. **`GET /api/v1/findings` and `GET /api/v1/findings/{id}`**
   (`presentation/routers/findings.py`) — surface the *existing*
   `CoreClient.list_findings` / `get_finding` over HTTP. No new business logic.
2. **`POST /api/v1/auth/dev-token`** (`presentation/routers/dev_auth.py`,
   `infrastructure/auth/dev_token.py`) — LOCAL-only test-token minting; disabled
   in production.
3. **Richer offline demo seed** (`infrastructure/core/stub_client.py`
   `demo_findings()`) — a superset of the canonical sample so the dashboard has
   realistic data offline. The canonical `sample_findings()` used by tests is
   unchanged.
4. **Static frontend mount** (`composition.build_app` → `_mount_frontend`) —
   serves `frontend/` at `/` when present.
5. **Settings** (`infrastructure/config/settings.py`) — `serve_frontend`,
   `enable_dev_login`, `core_demo_seed` (all default on for local; safe in prod).
6. **`scripts/mint_dev_token.py`** — CLI token minter for the paste-token flow.

None of these change the AI pipeline, the grounding guarantees, or tenant
isolation.

---

## 11. Migration path (optional, future)

The structure maps cleanly onto a framework port if ever wanted:
`api.js` → an API client/hooks layer; `store.js` → a store (Zustand/Redux);
`pages/*` → route components; `styles.css` tokens → a theme. Because the API
contract and the honest capability boundaries are already codified here, such a
port would be mechanical, not architectural.
