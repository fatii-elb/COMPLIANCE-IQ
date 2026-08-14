# ComplianceIQ — Web Console (Frontend)

A professional, enterprise-grade web console for the ComplianceIQ AI service. It
turns the backend's grounded GRC intelligence into a product a compliance team —
and a non-technical client — can actually use and verify.

> **One-line pitch:** find the problem → explain it (grounded & cited) → map it
> across frameworks → price the risk → propose a safe fix → report it to the
> board. Multi-tenant, auditable, and it refuses to guess.

---

## Quickstart (60 seconds)

```bash
# 1. from the project root
pip install -e .          # first time only
python -m complianceiq    # starts API + web console together

# 2. open the console
#    http://localhost:8000/

# 3. sign in
#    keep the pre-filled Developer sign-in (tenant-a / demo.analyst / Analyst)
#    click "Sign in"  →  Dashboard
```

That's it — one service, one URL, no build step, no database, works offline
(deterministic fake AI provider by default).

---

## Deliverables in this folder

| File | What it is |
|------|-----------|
| **README.md** (this file) | Overview + the two perspectives (developer / client) |
| **ARCHITECTURE.md** | Folder structure, services, API layer, state, auth, routing, styling, data flow, and the honest capability matrix |
| **CLIENT_TESTING_GUIDE.md** | Beginner, non-developer guide: start it, then 10 acceptance tests + troubleshooting |
| **ACCEPTANCE_CHECKLIST.md** | A tick-box functional checklist mapped to implemented features |
| **DEMO_SCRIPT.md** | A 10–15 minute client demonstration script |

---

## What's implemented (honest status)

| Capability | Status |
|-----------|--------|
| JWT authentication (verify), tenant isolation | ✅ IMPLEMENTED |
| Local developer sign-in (`/api/v1/auth/dev-token`) | ✅ IMPLEMENTED (dev/LOCAL only) |
| Findings list + detail (`/api/v1/findings…`) | ✅ IMPLEMENTED (surfaces the Core client) |
| Explain / Ask / Remediate / Correlate / Map / Financial / Report | ✅ IMPLEMENTED (the 8 AI endpoints) |
| Dashboard & risk aggregates (score, counts, coverage) | 🟡 PARTIAL — computed client-side (no aggregate endpoint) |
| Report draft generation | ✅ IMPLEMENTED |
| Report signed-PDF export / storage | ⚪ FUTURE — Markdown + print provided instead |
| Knowledge-base raw document browsing | ⚪ FUTURE — grounded lookup via `/ai/ask` provided |
| Findings write/delete | ⚪ NOT APPLICABLE — the Core Service owns writes (read-only consumer by design) |

Full detail and rationale: **ARCHITECTURE.md → §9**.

---

## Two perspectives

### 👩‍💻 Developer perspective — *"How does ComplianceIQ work internally?"*

The console is a **framework-free SPA** (ES modules + a CSS design system) served
as static files by the FastAPI app at the same origin, so there is no CORS and no
second server. Its internal shape mirrors the backend's Clean Architecture:

- **`api.js` is the only place `fetch` lives** — the frontend's "one gateway."
  It attaches the JWT, enforces timeouts, and normalises every failure into a
  typed `ApiError` with a client-safe message. UI code calls named functions
  (`aiEnrich`, `listFindings`, …), never raw HTTP.
- **`auth.js`** holds the session (token + decoded claims), persists it, and acts
  as the route guard; the token is verified **server-side** on every call — the
  frontend never trusts it beyond display.
- **`store.js`** caches the findings list once and memoises AI results per
  finding, and computes the dashboard/risk aggregates client-side (the backend
  exposes no aggregate endpoint).
- **`router.js` + `app.js`** own hash routing and the authenticated shell;
  **`pages/*`** are self-contained `render(mount, ctx)` modules.
- **`styles.css`** is one token-driven design system with dark + light themes and
  a consistent severity/risk colour language everywhere.

Under the hood, each AI action is a real call into the backend, where it passes
through the hardened **AI Gateway** (rate limit → budget → injection scan →
cache → routed model with retries/circuit-breaking → cost accounting) and the
**grounding pipeline** (retrieve → cite → verify → or abstain). The frontend
simply renders the honest result, including the `citation_verified` flag and
abstentions.

To integrate cleanly, a small **additive** set of backend endpoints was added
(findings read endpoints, a LOCAL-only dev-token endpoint, a static mount, a
richer offline demo seed). None change the AI pipeline or the security
guarantees, and all 282 backend tests still pass. See **ARCHITECTURE.md → §10**.

### 🏢 Client perspective — *"How do I use ComplianceIQ and verify it works?"*

You don't need to code. You start one service and open one web page:

1. Run `python -m complianceiq`, open `http://localhost:8000/`, and **Sign in**.
2. The **Dashboard** shows your compliance score, risk breakdown, framework
   coverage, and recent findings.
3. Open a **finding** to see what's wrong, why it matters (AI explanation with
   **verified citations**), which control it affects, and a proposed fix.
4. Ask the **AI Copilot** compliance questions — it answers with sources, and
   **abstains** rather than guess when it can't.
5. Generate a **report** for leadership and export it.

To *prove* it works, follow **CLIENT_TESTING_GUIDE.md** — ten step-by-step tests,
each telling you exactly what to click, what you should see, and how to know it
passed (with a troubleshooting section for anything that doesn't). Then tick off
**ACCEPTANCE_CHECKLIST.md**, and present it with **DEMO_SCRIPT.md**.

---

## Configuration knobs (optional)

| Env var | Default | Effect |
|---------|---------|--------|
| `CIQ_SERVE_FRONTEND` | `true` | Serve the console from the API |
| `CIQ_ENABLE_DEV_LOGIN` | `true` | Expose the LOCAL dev-token endpoint (off in prod automatically) |
| `CIQ_CORE_DEMO_SEED` | `true` | Seed the offline stub with the richer demo dataset |
| `CIQ_PORT` | `8000` | Change the port if 8000 is taken |
| `CIQ_ENVIRONMENT` | `local` | `production` disables dev-login entirely |

The defaults give a fully working offline demo with no external services.
