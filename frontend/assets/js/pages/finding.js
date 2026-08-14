// pages/finding.js — a single finding with its full detail and the four AI
// capabilities the backend offers for it, each a real call:
//   Explain     → POST /api/v1/ai/enrich      (EnrichedFinding: explanation + citations)
//   Map         → POST /api/v1/ai/map          (ControlMapping across frameworks)
//   Remediate   → POST /api/v1/ai/remediate    (RemediationProposal — never auto-applied)
//   Exposure    → POST /api/v1/ai/financial    (FinancialRiskAssessment in MAD)
// Results are memoised per finding so re-opening doesn't re-spend a model call.

import { icon } from "../icons.js";
import { findFinding } from "../store.js";
import { getFinding, aiEnrich, aiMap, aiRemediate, aiFinancial } from "../api.js";
import { cacheAi, getAi } from "../store.js";
import {
  esc, loadingState, errorState, severityBadge, statusBadge, frameworkLabel,
  cloudOf, cloudTag, domainLabel, fmtDateTime, mdLite, citationList, verifiedBadge,
  fmtMoney, setBusy, toast, copyText,
} from "../ui.js";

export default {
  async render(root, ctx) {
    const id = ctx.params.id;
    root.innerHTML = loadingState("Loading finding…");
    let f = findFinding(id);
    try {
      if (!f) f = await getFinding(id);
    } catch (err) {
      root.innerHTML = errorState(err);
      return;
    }
    ctx.setCrumb(prettyRule(f.rule_id), `Finding ${f.id}`);

    root.innerHTML = `
      <div class="page-head">
        <div class="ph-text">
          <button class="btn btn-sm btn-ghost mb" data-back><span style="display:inline-flex;transform:rotate(180deg)">${icon("chevronRight", 14)}</span> Back to findings</button>
          <h2>${esc(prettyRule(f.rule_id))}</h2>
          <div class="row wrap gap-sm mt">${severityBadge(f.severity)} ${statusBadge(f.status)} <span class="badge badge-brand">${esc(frameworkLabel(f.framework))} · ${esc(f.control_id)}</span> ${cloudTag(cloudOf(f))}</div>
        </div>
      </div>

      <div class="grid cols-3">
        <div class="card span-2">
          <div class="card-head"><h3>Overview</h3></div>
          <div class="card-body">
            <dl class="kv">
              <dt>Finding ID</dt><dd class="mono">${esc(f.id)}</dd>
              <dt>Resource</dt><dd class="mono" style="word-break:break-all">${esc(f.resource_id)}</dd>
              <dt>Cloud</dt><dd>${cloudTag(cloudOf(f))}</dd>
              <dt>Rule</dt><dd class="mono">${esc(f.rule_id)}</dd>
              <dt>Framework</dt><dd>${esc(frameworkLabel(f.framework))}</dd>
              <dt>Control</dt><dd class="mono">${esc(f.control_id)}</dd>
              <dt>Domain</dt><dd>${esc(domainLabel(f.domain))}</dd>
              <dt>Status</dt><dd>${statusBadge(f.status)}</dd>
              <dt>Detected</dt><dd>${esc(fmtDateTime(f.detected_at))}</dd>
            </dl>
            <div class="divider"></div>
            <div class="tiny muted mb">Rule-engine evidence</div>
            <pre class="code">${esc(JSON.stringify(f.evidence, null, 2))}</pre>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>Compliance mapping</h3></div>
          <div class="card-body">
            ${mappingChain(f)}
            <p class="tiny muted mt">This finding was raised by the Core rule engine against the control above. Use <b>Map controls</b> below to find equivalent controls in other frameworks.</p>
          </div>
        </div>
      </div>

      <div class="card mt-lg">
        <div class="card-head"><h3>${icon("spark", 16)} AI analysis</h3><span class="sub">Grounded in the compliance corpus — cited &amp; verified</span></div>
        <div class="card-body">
          <div class="row wrap gap-sm mb">
            <button class="btn btn-primary" data-ai="explain">${icon("copilot", 16)} Explain this finding</button>
            <button class="btn" data-ai="map">${icon("map", 16)} Map controls</button>
            <button class="btn" data-ai="remediate">${icon("bolt", 16)} Recommend remediation</button>
            <button class="btn" data-ai="financial">${icon("money", 16)} Financial exposure</button>
          </div>
          <div id="ai-result"></div>
        </div>
      </div>`;

    root.querySelector("[data-back]").addEventListener("click", () => ctx.navigate("/findings"));

    const resultBox = root.querySelector("#ai-result");
    const runners = {
      explain: { fn: () => aiEnrich([f]).then((r) => r[0]), render: renderExplain, label: "Explaining…" },
      map: { fn: () => aiMap(f), render: renderMap, label: "Mapping…" },
      remediate: { fn: () => aiRemediate(f), render: renderRemediate, label: "Generating fix…" },
      financial: { fn: () => aiFinancial(f), render: renderFinancial, label: "Quantifying…" },
    };

    root.querySelectorAll("[data-ai]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const kind = btn.dataset.ai;
        root.querySelectorAll("[data-ai]").forEach((b) => b.classList.toggle("btn-primary", b === btn));
        const cached = getAi(kind, f.id);
        if (cached) { resultBox.innerHTML = runners[kind].render(cached, f); wireResult(resultBox); return; }
        resultBox.innerHTML = loadingState(runners[kind].label);
        setBusy(btn, true, runners[kind].label);
        try {
          const res = await runners[kind].fn();
          cacheAi(kind, f.id, res);
          resultBox.innerHTML = runners[kind].render(res, f);
          wireResult(resultBox);
        } catch (err) {
          resultBox.innerHTML = errorState(err);
          toast({ title: "AI request failed", msg: err.message, kind: "err", timeout: 6000 });
        } finally {
          setBusy(btn, false);
        }
      })
    );

    // Auto-run the explanation — it's the primary action.
    root.querySelector('[data-ai="explain"]').click();
  },
};

/* ------------------------------- Renderers ------------------------------- */
function groundingBanner(verified, abstained) {
  if (abstained) return `<div class="notice warn mb">${icon("alert", 16)}<div><b>The copilot abstained.</b> The corpus didn't contain enough relevant, verifiable material to answer confidently — so it declined rather than guess.</div></div>`;
  return `<div class="mb">${verifiedBadge(verified)}</div>`;
}

function renderExplain(ef) {
  return `${groundingBanner(ef.citation_verified, false)}
    <div class="md">${mdLite(ef.explanation)}</div>
    <div class="divider"></div>
    <div class="tiny muted mb">Sources</div>${citationList(ef.citations)}`;
}

function renderMap(m) {
  const rows = (m.mappings || []).map((mc) => `<tr>
    <td>${esc(frameworkLabel(mc.framework))}</td><td class="mono">${esc(mc.control_id)}</td><td class="tiny muted">${esc(mc.reference)}</td></tr>`).join("");
  return `${groundingBanner(m.citation_verified, !m.citation_verified && !(m.mappings || []).length)}
    <div class="md mb">${mdLite(m.summary)}</div>
    ${rows ? `<div class="table-wrap"><table class="data" style="min-width:520px"><thead><tr><th>Framework</th><th>Equivalent control</th><th>Reference</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="muted small">No equivalent controls were confidently mapped.</p>'}
    <div class="divider"></div><div class="tiny muted mb">Sources</div>${citationList(m.citations)}`;
}

function renderRemediate(p) {
  return `<div class="notice mb">${icon("lock", 16)}<div><b>Proposal only — never auto-applied.</b> ComplianceIQ proposes the fix; a human approves and applies it in the Core platform. <span class="badge badge-muted" style="margin-left:6px">approved: ${p.approved}</span></div></div>
    <div class="tiny muted mb">Justification</div><div class="md mb">${mdLite(p.justification)}</div>
    <div class="row between"><div class="tiny muted">Proposed Terraform</div><button class="btn btn-sm btn-ghost" data-copy>${icon("copy", 14)} Copy</button></div>
    <pre class="code" id="tf">${esc(p.terraform)}</pre>
    <div class="divider"></div><div class="tiny muted mb">Sources</div>${citationList(p.citations)}`;
}

function renderFinancial(a) {
  return `<div class="grid cols-2 mb">
      <div class="card card-pad" style="background:var(--card-2)"><div class="stat-label">Estimated exposure</div>
        <div class="stat-value" style="font-size:24px">${fmtMoney(a.min_mad)} – ${fmtMoney(a.max_mad)}</div>
        <div class="stat-foot">Range, in Moroccan Dirham (MAD)</div></div>
      <div class="card card-pad" style="background:var(--card-2)"><div class="stat-label">Basis</div>
        <div class="small mt">${esc(a.finding_id ? "Single finding" : "Correlated risk")}</div>
        <div class="tiny muted mt">A defensible range — never a false-precision point estimate.</div></div>
    </div>
    <div class="tiny muted mb">Rationale</div><div class="md mb">${mdLite(a.rationale)}</div>
    ${(a.assumptions || []).length ? `<div class="tiny muted mb">Assumptions</div><ul>${a.assumptions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
}

function wireResult(box) {
  box.querySelector("[data-copy]")?.addEventListener("click", () => copyText(box.querySelector("#tf")?.textContent || ""));
}

function mappingChain(f) {
  const steps = [
    { t: "Finding", d: prettyRule(f.rule_id), ico: "findings" },
    { t: "Requirement", d: domainLabel(f.domain) + " control", ico: "shield" },
    { t: "Framework", d: frameworkLabel(f.framework), ico: "layers" },
    { t: "Control", d: f.control_id, ico: "check" },
  ];
  return `<div class="stack gap-sm">${steps.map((s, i) => `<div class="row gap-sm">
    <span class="af-ico" style="width:30px;height:30px">${icon(s.ico, 15)}</span>
    <div><div class="tiny muted">${esc(s.t)}</div><div style="font-weight:600" class="small">${esc(s.d)}</div></div>
  </div>${i < steps.length - 1 ? '<div style="margin-left:14px;color:var(--muted)">' + icon("chevronDown", 14) + "</div>" : ""}`).join("")}</div>`;
}

function prettyRule(ruleId = "") { return ruleId.replace(/^rule-/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
