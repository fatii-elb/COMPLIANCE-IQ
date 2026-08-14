# ComplianceIQ — Client Testing Guide

**Who this is for:** you, the client. You do **not** need to be a developer. This
guide walks you from a cold machine to a working ComplianceIQ console and shows
you, step by step, how to confirm the product does what it claims.

Every test tells you: what to do, **what you should see**, how to know it
**passed**, and **what to do if it fails**.

---

## Part 1 — Start ComplianceIQ

ComplianceIQ runs as one service that serves both the API and the web console.
You start it once, then open one web page.

### 1.1 What you need
- A machine with **Python 3.11+** and the project folder.
- A terminal (Command Prompt / PowerShell / Terminal).

### 1.2 Install (first time only)
From the project folder:
```bash
pip install -e .
```
> If your team already set this up, skip this step.

### 1.3 Start the service
From the project folder:
```bash
python -m complianceiq
```
**What you should see:** log lines ending with the service listening, e.g.
`starting_service … environment=local`. Leave this window open — it is the
running product.

**Pass:** the terminal stays open without crashing.
**If it fails:** see *Troubleshooting → Frontend does not start* at the end.

### 1.4 Open the console
In your browser, go to:
```
http://localhost:8000/
```
**What you should see:** a dark **"Sign in"** screen with the ComplianceIQ logo
and a marketing panel on the left ("Grounded compliance intelligence…").

**Pass:** the sign-in screen appears.
**If it fails:** the page is blank or won't load → see *Troubleshooting → Blank
page* and *API connection failure*.

---

## Part 2 — The ten acceptance tests

Do these in order. Each is self-contained.

---

### ✅ Test 1 — Sign in
```
Open ComplianceIQ  →  Enter credentials  →  Sign in  →  Dashboard appears
```
1. On the sign-in screen, keep the **Developer sign-in** tab selected.
2. Leave the pre-filled values: Tenant `tenant-a`, User `demo.analyst@acme.example`, Role `Analyst`.
3. Click **Sign in**.

**Expected result:** you are taken to the **Dashboard**. Top-right shows your
user avatar (`DA`) and a green **"local · v0.1.0"** status pill. A "Welcome"
toast appears briefly.

**Passed if:** the Dashboard loads and the status pill is **green** (not "offline").
**If it fails:** a red "Sign-in failed" toast → the backend isn't running or the
dev-login is disabled; confirm Part 1 and that the environment is `local`.

---

### ✅ Test 2 — View the compliance dashboard
Look at the Dashboard (the page you just landed on). Verify each area:

| Area | What you should see |
|------|---------------------|
| Top row tiles | **Compliance score** (a number 0–100), **Open findings**, **Critical**, **High risk** |
| Compliance score card | A circular gauge showing the same score |
| Risk overview card | A donut of open findings split by severity + a legend (Critical/High/Medium/Low with counts) |
| Framework coverage | Bars for NIST CSF, ISO 27001, Loi 05-20, DNSSI, SOC 2, plus a cloud distribution (AWS/Azure/GCP) |
| Recent findings | A table of the latest findings with severity, cloud, framework, status, date |
| AI Insight | A card with a **Generate insight** button |

**Passed if:** all six areas show data (numbers and charts), not blanks or errors.
**If it fails:** an "Unable to load" panel with a **Try again** button → click it;
if it persists, see *Data not loading* in Troubleshooting.

---

### ✅ Test 3 — Inspect a finding
```
Dashboard  →  Findings  →  Select a finding  →  Finding details
```
1. Click **Findings** in the left sidebar.
2. In the table, click any row (e.g. **Sg Open Ingress**, severity *Critical*).
3. You are taken to the **finding detail** page.

**Expected result — you can understand:**
- **What is wrong** — the Overview panel (resource, rule, evidence like
  `"actual": "0.0.0.0/0 on :22"`).
- **Why it matters** — the AI **explanation** auto-loads under "AI analysis".
- **Which requirement is affected** — the "Compliance mapping" chain
  (Finding → Requirement → Framework → Control).
- **What should be done** — click **Recommend remediation** (Test after this).

**Passed if:** the detail page shows the finding's data **and** an AI explanation
appears with a green **"Grounded & Verified"** badge.
**If it fails:** if the AI panel shows an error, retry; see *AI request fails*.

---

### ✅ Test 4 — Ask the AI Copilot
1. Click **AI Copilot** in the sidebar.
2. Type a question, e.g.:
   > *Why is an open security group a compliance risk?*

   or *What does ISO 27001 require for access control?*
3. Press **Enter** (or click **Send**).

**Expected result:** your question appears as a chat bubble; the copilot shows a
"Retrieving & grounding…" indicator, then replies with a plain-language answer.

**A good answer contains:**
- a clear, relevant explanation (not a refusal, not gibberish),
- a **grounding flag** ("Grounded & verified" or "Answer not verified"),
- a **Sources** list of specific controls.

**Passed if:** you get a relevant answer **with a Sources list**.
**If it fails:** a "Couldn't answer" bubble → retry; if repeated, see *AI request
fails*.

---

### ✅ Test 5 — Verify citations (is the answer really grounded?)
Using the copilot answer from Test 4:
1. Look at the **Sources** section under the answer.
2. Each source names a **framework** (e.g. *ISO 27001*, *DNSSI*) and a **control
   ID** (e.g. *A.5.17*, *DNSSI-ACC*) with a short reference.
3. Look for the green **"Grounded & verified"** flag.

**How to know it's genuinely grounded:** the green flag means the system checked
every citation against the source corpus — the answer is not invented. If instead
you see **"Abstained — no confident grounding"**, that is *also correct
behaviour*: the copilot declined rather than guess. Try a compliance-specific
question to get a grounded answer.

**Passed if:** grounded answers list real controls, and off-topic questions
abstain (see Test 6).

---

### ✅ Test 6 — Ask an unsupported / irrelevant question
1. In the Copilot, ask something outside compliance, e.g.:
   > *What's a good recipe for tagine?*
2. Send it.

**Expected result:** the copilot **abstains** — you should see an
**"Abstained — no confident grounding"** flag and a message that it declined for
lack of relevant sources. It should **not** invent a confident answer.

**Passed if:** the system abstains (or clearly says it can't help) instead of
fabricating.
**If it fails:** if it confidently answers an unrelated question with fake
citations, flag it — that would violate the grounding guarantee.

---

### ✅ Test 7 — Authentication failures
Test that the product protects itself.

**a) Invalid token**
1. Sign out (avatar menu top-right → **Sign out**).
2. On the sign-in screen, choose the **Paste a token** tab.
3. Paste nonsense: `not.a.token` and click **Use token**.
**Expected:** a red "Invalid token" message; you are **not** signed in.

**b) Missing authentication (protected data can't be reached)**
1. While signed out, try to open a data URL directly in the browser:
   ```
   http://localhost:8000/api/v1/findings
   ```
**Expected:** a JSON error `{"error":{"code":"authentication_error",…}}` with
HTTP **401** — the API refuses without a valid token.

**c) Expired token** (optional)
- Dev tokens last 2 hours. If you leave the app open past expiry, ComplianceIQ
  shows a **"Session expired"** message and returns you to sign-in.

**Passed if:** invalid/missing credentials are rejected and protected data is
never shown without a valid token.

---

### ✅ Test 8 — Backend downtime is handled gracefully
1. Go back to the terminal running the service and **stop it** (press
   `Ctrl+C`).
2. In the browser, click **Refresh** on the Findings page (or navigate between
   pages).

**Expected result:** instead of a broken page, you see a friendly message such
as *"ComplianceIQ can't reach the backend service. Check that it's running…"* and
the top-right status pill turns to **"offline"** (red dot).

3. **Restart** the service (`python -m complianceiq`) and click **Try again** /
   **Recheck** (Settings page) — data returns and the pill goes green again.

**Passed if:** downtime shows a helpful message (no raw stack trace) and recovery
is automatic when the backend returns.

---

### ✅ Test 9 — Search, filter, and sort findings
1. Go to **Findings**.
2. **Search:** type `iam` in the search box → the list narrows to IAM-related
   findings.
3. **Filter:** set **Severity = Critical** → only critical findings remain; the
   count ("X of 12 findings") updates.
4. **Filter:** set **Framework = ISO 27001** → only ISO findings remain.
5. **Sort:** click the **Severity** column header → order flips (asc/desc).
6. Click **Reset** → all findings return.

**Passed if:** search, each filter, and sorting all change the table correctly and
the result count updates.

---

### ✅ Test 10 — Reports
1. Click **Reports** in the sidebar.
2. Leave scope as **All open findings**.
3. Click **Generate report**.

**Expected result:** a two-step progress ("Enriching findings…" → "Drafting the
executive summary…"), then a **Compliance Report** card showing:
- Findings covered (a count),
- a **Severity breakdown** bar chart,
- an **Executive summary** paragraph.

4. In the page header, click **Markdown** to download the report, or **Print** to
   print/save as PDF from your browser.

**Passed if:** a report is generated with a summary and severity breakdown, and
the download/print buttons work.
**Note:** a *signed server-side PDF* is a future backend feature; Markdown/print
is the current, honest export.

---

## Part 3 — Quick pass/fail summary

If Tests 1–10 all pass, the product is working end-to-end: authentication,
dashboard, findings, AI explanation, grounded copilot with citations, abstention,
error handling, search/filter, and reporting.

Keep going to the **Acceptance Checklist** (`ACCEPTANCE_CHECKLIST.md`) to tick off
every item formally, and the **Demo Script** (`DEMO_SCRIPT.md`) to present it.

---

## Part 4 — Troubleshooting

For each problem: **cause → how to verify → how to fix.**

### Frontend does not start / `python -m complianceiq` errors
- **Cause:** dependencies not installed, or wrong Python version.
- **Verify:** run `python --version` (need 3.11+); read the error in the terminal.
- **Fix:** `pip install -e .` from the project folder, then retry.

### Blank page at `http://localhost:8000/`
- **Cause:** the frontend static files weren't served, or the browser cached a
  half-load.
- **Verify:** open `http://localhost:8000/health` — it should return
  `{"status":"ok",…}`. Open the browser console (F12) and look for red errors.
- **Fix:** hard-refresh (Ctrl+Shift+R). Confirm the terminal shows the service
  running. Ensure you opened the root `/`, not a sub-path directly.

### "Backend unreachable" / status pill is offline
- **Cause:** the service isn't running, or a firewall/port conflict.
- **Verify:** is the `python -m complianceiq` terminal still open? Try
  `http://localhost:8000/health`.
- **Fix:** restart the service. If port 8000 is busy, set `CIQ_PORT=8080` and open
  `http://localhost:8080/`.

### CORS error in the browser console
- **Cause:** you are serving the frontend from a **different** origin than the API.
- **Verify:** the address bar should be `http://localhost:8000/` (same service).
- **Fix:** use the bundled setup (open the backend's own URL). The same-origin
  setup needs no CORS. (Only relevant if someone hosts the frontend separately.)

### Sign-in fails ("Sign-in failed")
- **Cause:** dev-login is disabled or the environment is production.
- **Verify:** the sign-in screen's footer shows `Backend online · local · v…`.
- **Fix:** run in the `local` environment (default). In production, use the
  **Paste a token** tab with a real Core-issued token.

### AI request fails (explain / ask / report)
- **Cause:** a transient model/provider error, or a rate/budget limit for the
  tenant.
- **Verify:** the error toast/message; check the service terminal for warnings.
- **Fix:** click **Try again**. The default offline setup uses a deterministic
  fake provider, so repeated failures usually mean the service was restarting.

### Data not loading (findings empty)
- **Cause:** the offline demo seed is disabled, or you signed in as a tenant with
  no findings.
- **Verify:** sign in with tenant **`tenant-a`** (the seeded demo tenant).
- **Fix:** use `tenant-a`. Other tenants legitimately show **empty states**
  (this proves tenant isolation, not a bug).

### Environment variable missing / wrong config
- **Cause:** a custom `.env` overrode a default.
- **Verify:** check for a `.env` file in the project folder.
- **Fix:** the defaults work out of the box; remove overrides you didn't intend.

### Backend / database unavailable
- **Cause:** in the default **offline** setup there is **no external database** —
  everything runs in-process, so this shouldn't occur. If configured for a real
  Core/Postgres, that dependency may be down.
- **Verify:** open **Settings → Connection → Recheck**; unhealthy dependencies are
  listed there, and `GET /health/ready` returns 503.
- **Fix:** start the dependency, or switch back to the offline defaults
  (`CIQ_CORE_CLIENT=stub`, `CIQ_VECTOR_STORE=memory`).
