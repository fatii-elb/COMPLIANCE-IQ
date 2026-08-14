# ComplianceIQ — Acceptance Testing Checklist

Tick each item as you verify it in the running console
(`http://localhost:8000/`). Items are grouped by area and reflect the
**actually implemented** features. Items marked _(future)_ are intentionally not
implemented yet and are listed so the scope is explicit.

Sign in as **tenant `tenant-a`**, user `demo.analyst@acme.example`, role
**Analyst** unless a test says otherwise.

---

## Authentication
- [ ] Developer sign-in works and lands on the Dashboard
- [ ] The user avatar and tenant (`tenant-a`) show in the top bar / sidebar footer
- [ ] "Paste a token" tab accepts a valid JWT
- [ ] Invalid token (`not.a.token`) is **rejected** with a clear message
- [ ] Protected API (`/api/v1/findings`) returns **401** when signed out
- [ ] Sign out works and returns to the sign-in screen
- [ ] Protected pages cannot be reached without a session (router redirects to login)
- [ ] Expired session shows a "Session expired" message and returns to sign-in

## Dashboard
- [ ] Dashboard loads without errors
- [ ] Compliance **score** tile and gauge display a number 0–100
- [ ] Open / Critical / High **risk metrics** display
- [ ] **Risk overview** donut + severity legend display with counts
- [ ] **Framework coverage** bars display (NIST CSF, ISO 27001, Loi 05-20, DNSSI, SOC 2)
- [ ] **Cloud distribution** (AWS/Azure/GCP) displays
- [ ] **Recent findings** table displays and rows are clickable
- [ ] **AI Insight → Generate insight** returns a systemic-risk narrative

## Findings
- [ ] Findings list loads (12 demo findings for `tenant-a`)
- [ ] **Search** narrows results (e.g. `iam`)
- [ ] **Severity** filter works
- [ ] **Framework** filter works
- [ ] **Status** filter works
- [ ] Column **sorting** works (e.g. Severity, Detected)
- [ ] **Reset** clears filters and search
- [ ] Result count ("X of 12") updates with filters
- [ ] Clicking a row opens the **finding detail**
- [ ] Severity, status, cloud, and framework are displayed correctly and consistently

## Finding detail
- [ ] Overview shows resource, rule, framework, control, domain, status, detected date
- [ ] Rule-engine **evidence** is shown
- [ ] **Compliance mapping** chain (Finding → Requirement → Framework → Control) displays
- [ ] **Explain this finding** auto-loads a grounded explanation
- [ ] Explanation shows a **Grounded & Verified** (or Not verified) badge
- [ ] Explanation lists **Sources** (citations)
- [ ] **Map controls** returns equivalent controls across frameworks
- [ ] **Recommend remediation** returns Terraform + justification, marked `approved: false`
- [ ] **Financial exposure** returns a MAD range + rationale + assumptions
- [ ] Re-opening the finding does not re-run the calls (memoised)

## AI Copilot
- [ ] Chat loads with suggested questions
- [ ] A question can be submitted (Enter or Send)
- [ ] A **loading** ("Retrieving & grounding…") state shows
- [ ] An AI answer appears, visually distinct from the user message
- [ ] Answer shows a **grounding flag** (verified / not verified / abstained)
- [ ] **Citations / Sources** appear for grounded answers
- [ ] An **off-topic** question causes an **abstention** (no fabricated answer)
- [ ] Framework **scope** selector can restrict retrieval
- [ ] Errors are handled with a clear "Couldn't answer" message (no stack trace)

## Risk
- [ ] Severity distribution, risk-by-domain, and risk-by-framework charts display
- [ ] **Correlate top findings** returns a grounded systemic-risk narrative
- [ ] **Financial exposure** for a chosen finding returns a MAD range + rationale

## Frameworks & Controls
- [ ] Framework coverage cards display with pass %
- [ ] ISO copyright note is shown (identifiers/summaries only)
- [ ] **Map control** for a finding returns equivalents + citations

## Knowledge Base
- [ ] Grounding explanation and corpus coverage display
- [ ] **Grounded lookup** returns an answer with citations (or an abstention)
- [ ] Raw-document browsing is clearly marked **Not implemented (future)**

## Reports
- [ ] Report scope can be chosen
- [ ] **Generate report** runs enrich → report and shows progress
- [ ] Report shows finding count, severity breakdown, and executive summary
- [ ] **Markdown** download works
- [ ] **Print** works
- [ ] Signed PDF export is understood to be **future** (not implemented)

## Settings
- [ ] Session details (user, tenant, roles, token expiry) display
- [ ] Token can be copied (masked preview)
- [ ] Connection card shows service, version, environment, readiness + dependencies
- [ ] Theme toggle (Dark / Light) works and persists across reload
- [ ] Sign out works

## UX & quality
- [ ] Responsive layout works on desktop, tablet, and mobile (sidebar → drawer)
- [ ] Light and dark themes both render cleanly
- [ ] No broken pages when navigating between all sections
- [ ] **No console errors** during normal use (verified: 0 in the e2e run)
- [ ] **Loading** states show during data/AI fetches
- [ ] **Empty** states show for filtered-to-nothing and other-tenant data
- [ ] **Error** states show friendly messages (no raw technical errors)
- [ ] **Success** states (toasts) confirm actions (sign-in, refresh, copy, report)
- [ ] Backend **offline** is handled gracefully and recovers automatically

## Security guarantees (spot-check)
- [ ] Signing in as a different tenant (e.g. `tenant-b`) shows **empty** findings (isolation)
- [ ] Remediation proposals are always `approved: false` (never auto-applied)
- [ ] The copilot abstains rather than fabricate when the corpus lacks the answer
