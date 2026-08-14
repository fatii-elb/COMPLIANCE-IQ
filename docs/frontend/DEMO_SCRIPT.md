# ComplianceIQ — Client Demo Script (10–15 minutes)

A realistic walkthrough for presenting ComplianceIQ to a company. Each step
tells you **what to click**, **what to say**, **what the audience sees**, and
**what capability you're proving**.

**Before you start:** run `python -m complianceiq`, open
`http://localhost:8000/`, and be signed out (fresh sign-in makes a better demo).
Total time ≈ 12 minutes.

---

### 1. Sign in  ·  ~30s
- **Click:** keep *Developer sign-in*, click **Sign in** (tenant `tenant-a`).
- **Say:** *"ComplianceIQ is a multi-tenant GRC platform. I'm signing in as an
  analyst at a tenant organisation. Authentication is JWT-based and every action
  is scoped to this tenant."*
- **Audience sees:** the sign-in screen, then the Dashboard with a green backend
  status pill.
- **Proves:** authentication and tenant-scoped access.

### 2. Open the Dashboard  ·  ~1.5m
- **Click:** nothing — you're on it. Point across the page.
- **Say:** *"This is the compliance posture at a glance: an overall score, open
  findings by severity, coverage across the frameworks we support — ISO 27001,
  NIST CSF, SOC 2, and the Moroccan Loi 05-20 and DNSSI — and the spread across
  AWS, Azure, and GCP."*
- **Audience sees:** score gauge, severity donut, framework and cloud bars,
  recent findings.
- **Proves:** at-a-glance executive overview across multi-cloud, multi-framework.

### 3. Explain the compliance posture  ·  ~1m
- **Say:** *"We have a weighted compliance score, with the critical and high-risk
  findings surfaced first. The point isn't just to count problems — it's to
  explain and prioritise them, which is where the AI comes in."*
- **Proves:** the product frames risk, not just raw data.

### 4. Open a critical finding  ·  ~1.5m
- **Click:** **Findings** → click **Sg Open Ingress** (Critical).
- **Say:** *"Here's a critical finding — a security group open to the whole
  internet on SSH. The Core scanner produced the raw verdict and evidence. Notice
  the compliance mapping: this finding ties to a specific control in NIST CSF."*
- **Audience sees:** overview, evidence JSON, mapping chain.
- **Proves:** findings carry real evidence and map to controls.

### 5. Explain the risk (AI)  ·  ~1.5m
- **Click:** nothing — the **AI explanation auto-loads**. Point to it.
- **Say:** *"ComplianceIQ has automatically explained, in plain language, why this
  matters — and crucially it's marked **Grounded & Verified**. Every claim is
  backed by a real control the system actually retrieved. It doesn't hallucinate."*
- **Audience sees:** the explanation + the green verified badge.
- **Proves:** explainable, grounded AI.

### 6. Show the compliance citations  ·  ~1m
- **Click:** scroll to **Sources** under the explanation.
- **Say:** *"These are the citations — the exact framework controls the
  explanation is grounded in. An auditor can follow them. If the system can't
  find grounding, it refuses to answer rather than guess — I'll show that in a
  moment."*
- **Proves:** auditable citations, the core trust feature.

### 7. Ask for remediation  ·  ~1.5m
- **Click:** **Recommend remediation**.
- **Say:** *"Now the fix: ComplianceIQ proposes Infrastructure-as-Code —
  Terraform — with a grounded justification. Notice it's explicitly marked
  `approved: false`. The platform **proposes**; a human **approves** and applies
  it. It never changes your infrastructure automatically."*
- **Audience sees:** Terraform block + justification + the not-applied notice.
- **Proves:** actionable remediation with a human-in-the-loop safety guarantee.

### 8. Review the financial exposure  ·  ~1m
- **Click:** **Financial exposure**.
- **Say:** *"We translate technical risk into money — a defensible exposure range
  in Dirham, with the rationale and assumptions spelled out. A range, never a
  false-precision single number."*
- **Proves:** business-level risk quantification.

### 9. Ask the AI Copilot (grounding + abstention)  ·  ~2m
- **Click:** **AI Copilot**. Ask: *"What does ISO 27001 require for access
  control?"* → **Send**.
- **Say:** *"This is the analyst's assistant — grounded answers with sources."*
- **Then ask something off-topic:** *"What's a good tagine recipe?"* → **Send**.
- **Say:** *"And here's the trust guarantee in action: for anything outside its
  compliance knowledge, it **abstains** instead of making something up."*
- **Audience sees:** a cited answer, then an abstention.
- **Proves:** grounded copilot with honest refusal — the differentiator vs. a
  generic chatbot.

### 10. Generate an executive report  ·  ~1.5m
- **Click:** **Reports** → **Generate report**.
- **Say:** *"Finally, the board-level output. ComplianceIQ enriches the findings
  with grounded explanations, then drafts an executive summary with a severity
  breakdown — exportable to share with leadership or an auditor."*
- **Audience sees:** the two-step generation, then the report with summary and
  breakdown; click **Markdown** or **Print** to show export.
- **Proves:** the full loop from raw finding to executive reporting.

---

### Closing line
> *"That's ComplianceIQ end to end: it finds the problem, explains it in grounded
> and cited language, maps it across your frameworks, prices the risk, proposes a
> safe fix, and reports it to your board — all multi-tenant, all auditable, and it
> refuses to guess. Every AI action runs through one hardened gateway that's
> rate-limited, budgeted, and injection-scanned."*

### Optional extras (if you have time / questions)
- **Frameworks & Controls → Map control** — cross-framework equivalence.
- **Risk → Correlate top findings** — one systemic-risk narrative across findings.
- **Settings → Connection** — show live backend health and version.
- **Theme toggle** — dark/light for different room lighting.
- **Tenant isolation** — sign out, sign in as `tenant-b`: findings are empty,
  proving strict data separation.
