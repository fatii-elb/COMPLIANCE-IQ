// pages/risk.js — risk analytics + two real AI capabilities:
//   Systemic risk  → POST /api/v1/ai/correlate  (a grounded narrative over many findings)
//   Exposure       → POST /api/v1/ai/financial  (a MAD range for a chosen finding)
// Distribution charts are computed client-side from the findings list.

import { icon } from "../icons.js";
import { loadFindings, computeMetrics, severityRank } from "../store.js";
import { aiCorrelate, aiFinancial } from "../api.js";
import {
  esc, loadingState, errorState, mdLite, fmtMoney, severityBadge,
  frameworkLabel, setBusy, toast,
} from "../ui.js";
import { severityDonut, barList } from "../charts.js";
import { SEVERITY, DOMAINS } from "../config.js";

export default {
  async render(root, ctx) {
    root.innerHTML = loadingState("Loading risk analytics…");
    let findings;
    try { findings = await loadFindings(); }
    catch (err) { root.innerHTML = errorState(err); return; }

    const m = computeMetrics(findings);
    const fails = findings.filter((f) => f.status === "fail");
    const topOpen = [...fails].sort((a, b) => severityRank(b.severity) - severityRank(a.severity)).slice(0, 8);
    const domainRows = Object.entries(m.byDomain).sort((a, b) => b[1] - a[1]).map(([d, n]) => ({ label: DOMAINS[d] || d, value: n, color: "var(--sev-high)" }));
    const domainsAffected = Object.keys(m.byDomain).length;

    root.innerHTML = `
      <div class="page-head"><div class="ph-text"><h2>Risk Analysis</h2><p>Understand systemic risk across findings and quantify the business exposure in Moroccan Dirham (MAD).</p></div></div>

      <div class="grid cols-3 mb">
        <div class="card card-pad stat accent-critical"><div class="stat-ico">${icon("alert", 18)}</div><div class="stat-label">Critical + High</div><div class="stat-value tabnums">${m.bySeverity.critical + m.bySeverity.high}</div><div class="stat-foot">of ${m.open} open findings</div></div>
        <div class="card card-pad stat"><div class="stat-ico">${icon("layers", 18)}</div><div class="stat-label">Domains affected</div><div class="stat-value tabnums">${domainsAffected}</div><div class="stat-foot">${Object.keys(DOMAINS).length} tracked domains</div></div>
        <div class="card card-pad stat accent-high"><div class="stat-ico">${icon("risk", 18)}</div><div class="stat-label">Risk score</div><div class="stat-value tabnums">${100 - m.score}</div><div class="stat-foot">Higher = more exposure</div></div>
      </div>

      <div class="grid cols-3 mb">
        <div class="card"><div class="card-head"><h3>Severity distribution</h3></div><div class="card-body center">${severityDonut(m.bySeverity)}
          <div class="row wrap gap-sm mt" style="justify-content:center">${["critical", "high", "medium", "low"].map((s) => `<span class="chip"><span class="legend-dot" style="background:${SEVERITY[s].color}"></span>${SEVERITY[s].label} ${m.bySeverity[s]}</span>`).join("")}</div></div></div>
        <div class="card"><div class="card-head"><h3>Risk by domain</h3><span class="sub">Open findings</span></div><div class="card-body">${domainRows.length ? barList(domainRows) : '<p class="muted small">No open findings.</p>'}</div></div>
        <div class="card"><div class="card-head"><h3>Risk by framework</h3><span class="sub">Open findings</span></div><div class="card-body">${Object.entries(m.byFramework).some(([, v]) => v.fail) ? barList(Object.entries(m.byFramework).map(([fw, v]) => ({ label: frameworkLabel(fw), value: v.fail, color: "var(--brand-grad)" })).filter((r) => r.value)) : '<p class="muted small">—</p>'}</div></div>
      </div>

      <div class="grid cols-2">
        <div class="card">
          <div class="card-head"><h3>${icon("spark", 15)} Systemic risk correlation</h3></div>
          <div class="card-body" id="corr">
            <p class="muted small">Correlate your ${topOpen.length} highest-severity open findings into one grounded, executive-ready narrative that explains how they compound.</p>
            <button class="btn btn-primary mt" id="corr-btn" ${topOpen.length ? "" : "disabled"}>${icon("spark", 16)} Correlate top findings</button>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>${icon("money", 15)} Financial exposure</h3></div>
          <div class="card-body">
            <label class="label">Choose a finding to quantify</label>
            <div class="input-group">
              <select class="select" id="fin-sel">${fails.map((f) => `<option value="${esc(f.id)}">${esc(prettyRule(f.rule_id))} — ${f.severity}</option>`).join("") || '<option value="">No open findings</option>'}</select>
              <button class="btn btn-primary" id="fin-btn" ${fails.length ? "" : "disabled"}>${icon("scale", 16)} Estimate</button>
            </div>
            <div id="fin-result" class="mt"></div>
          </div>
        </div>
      </div>`;

    // Correlate
    root.querySelector("#corr-btn")?.addEventListener("click", async (e) => {
      const btn = e.currentTarget; setBusy(btn, true, "Correlating…");
      try {
        const res = await aiCorrelate(topOpen);
        root.querySelector("#corr").innerHTML = `<div class="mb tiny muted">Across ${topOpen.length} findings</div><div class="md">${mdLite(res.narrative)}</div>`;
      } catch (err) { setBusy(btn, false); toast({ title: "Correlation failed", msg: err.message, kind: "err", timeout: 6000 }); }
    });

    // Financial
    root.querySelector("#fin-btn")?.addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      const id = root.querySelector("#fin-sel").value;
      const f = fails.find((x) => x.id === id);
      if (!f) return;
      const box = root.querySelector("#fin-result");
      box.innerHTML = loadingState("Quantifying exposure…");
      setBusy(btn, true, "Estimating…");
      try {
        const a = await aiFinancial(f);
        box.innerHTML = `<div class="card card-pad" style="background:var(--card-2)">
          <div class="row between mb">${severityBadge(f.severity)}<span class="tiny muted">${esc(prettyRule(f.rule_id))}</span></div>
          <div class="stat-value" style="font-size:24px">${fmtMoney(a.min_mad)} – ${fmtMoney(a.max_mad)}</div>
          <div class="stat-foot">Estimated exposure range (MAD)</div>
          <div class="divider"></div>
          <div class="tiny muted mb">Rationale</div><div class="md small">${mdLite(a.rationale)}</div>
          ${(a.assumptions || []).length ? `<div class="tiny muted mt mb">Assumptions</div><ul class="small">${a.assumptions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        </div>`;
      } catch (err) { box.innerHTML = errorState(err); toast({ title: "Estimate failed", msg: err.message, kind: "err" }); }
      finally { setBusy(btn, false); }
    });
  },
};

function prettyRule(r = "") { return r.replace(/^rule-/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
