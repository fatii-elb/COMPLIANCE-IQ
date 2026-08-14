// pages/dashboard.js — the executive overview. All metrics are computed
// client-side from GET /api/v1/findings (the backend exposes no aggregate
// endpoint — see the architecture doc). The AI Insight is an on-demand real call
// to POST /api/v1/ai/correlate over the top open findings.

import { icon } from "../icons.js";
import { loadFindings, computeMetrics, severityRank } from "../store.js";
import { aiCorrelate } from "../api.js";
import {
  esc, loadingState, errorState, severityBadge, statusBadge, frameworkLabel,
  cloudOf, cloudTag, fmtDate, relTime, mdLite, setBusy, toast,
} from "../ui.js";
import { scoreDonut, severityDonut, barList } from "../charts.js";
import { FRAMEWORKS, SEVERITY, CLOUDS } from "../config.js";

function statTile({ label, value, foot, ico, accent = "" }) {
  return `<div class="card card-pad stat ${accent}">
    <div class="stat-ico">${icon(ico, 18)}</div>
    <div class="stat-label">${esc(label)}</div>
    <div class="stat-value tabnums">${value}</div>
    <div class="stat-foot">${foot}</div>
  </div>`;
}

export default {
  async render(root, ctx) {
    root.innerHTML = loadingState("Loading compliance posture…");
    let findings;
    try {
      findings = await loadFindings();
    } catch (err) {
      root.innerHTML = errorState(err, 'data-retry="1"');
      root.querySelector("[data-retry]")?.addEventListener("click", () => this.render(root, ctx));
      return;
    }
    ctx.setNavBadge("findings", findings.length);

    const m = computeMetrics(findings);
    const recent = [...findings].sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at)).slice(0, 6);
    const topOpen = findings.filter((f) => f.status === "fail").sort((a, b) => severityRank(b.severity) - severityRank(a.severity)).slice(0, 8);

    const fwRows = Object.entries(m.byFramework)
      .sort((a, b) => b[1].fail - a[1].fail)
      .map(([fw, v]) => ({ label: frameworkLabel(fw), value: v.fail, color: "var(--sev-high)", total: v.total }));

    const cloudCounts = {};
    for (const f of findings) { const c = cloudOf(f); cloudCounts[c] = (cloudCounts[c] || 0) + 1; }
    const cloudRows = Object.entries(cloudCounts).map(([c, n]) => ({ label: CLOUDS[c]?.label || c, value: n, color: CLOUDS[c]?.color || "var(--brand)" }));

    root.innerHTML = `
      <div class="grid cols-4 mb">
        ${statTile({ label: "Compliance score", value: m.score, foot: `Weighted across ${m.total} checks`, ico: "shield", accent: m.score >= 80 ? "accent-ok" : "" })}
        ${statTile({ label: "Open findings", value: m.open, foot: `${m.resolved} passing`, ico: "findings" })}
        ${statTile({ label: "Critical", value: m.bySeverity.critical, foot: "Require immediate action", ico: "alert", accent: "accent-critical" })}
        ${statTile({ label: "High risk", value: m.bySeverity.high, foot: "Prioritise this sprint", ico: "risk", accent: "accent-high" })}
      </div>

      <div class="grid cols-3 mb">
        <div class="card">
          <div class="card-head"><h3>Compliance score</h3></div>
          <div class="card-body"><div class="score-wrap">
            ${scoreDonut(m.score)}
            <div class="score-legend">
              <div class="legend-row"><span class="badge badge-ok">${m.resolved}</span> Passing checks</div>
              <div class="legend-row"><span class="badge badge-fail">${m.open}</span> Open findings</div>
              <p class="tiny muted" style="max-width:190px">A transparent, weighted summary of open failures. Not a certification score.</p>
            </div></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>Risk overview</h3><span class="sub">Open by severity</span></div>
          <div class="card-body"><div class="score-wrap">
            ${severityDonut(m.bySeverity)}
            <div class="score-legend">
              ${["critical", "high", "medium", "low"].map((s) => `<div class="legend-row"><span class="legend-dot" style="background:${SEVERITY[s].color}"></span> ${SEVERITY[s].label} <b class="tabnums" style="margin-left:auto">${m.bySeverity[s]}</b></div>`).join("")}
            </div></div>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>Framework coverage</h3><span class="sub">Open findings</span></div>
          <div class="card-body">
            ${fwRows.length ? barList(fwRows) : '<p class="muted small">No framework data.</p>'}
            <div class="divider"></div>
            <div class="tiny muted">Cloud distribution</div>
            <div class="mt">${cloudRows.length ? barList(cloudRows) : '<p class="muted small">—</p>'}</div>
          </div>
        </div>
      </div>

      <div class="grid cols-3 mb">
        <div class="card span-2">
          <div class="card-head"><h3>Recent findings</h3><div class="card-actions"><button class="btn btn-sm btn-ghost" data-go="/findings">View all ${icon("chevronRight", 14)}</button></div></div>
          <div class="table-wrap">
            <table class="data">
              <thead><tr><th>Finding</th><th>Severity</th><th>Cloud</th><th>Framework</th><th>Status</th><th>Detected</th></tr></thead>
              <tbody>
                ${recent.map((f) => `<tr data-id="${esc(f.id)}">
                  <td><div style="font-weight:600">${esc(prettyRule(f.rule_id))}</div><div class="tiny muted mono truncate">${esc(f.resource_id)}</div></td>
                  <td>${severityBadge(f.severity)}</td>
                  <td>${cloudTag(cloudOf(f))}</td>
                  <td><span class="tiny">${esc(frameworkLabel(f.framework))}</span><div class="tiny muted mono">${esc(f.control_id)}</div></td>
                  <td>${statusBadge(f.status)}</td>
                  <td class="tiny muted" title="${esc(fmtDate(f.detected_at))}">${esc(relTime(f.detected_at))}</td>
                </tr>`).join("")}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-head"><h3>AI Insight</h3><span class="badge badge-brand">${icon("spark", 13)} Live</span></div>
          <div class="card-body" id="ai-insight">
            <p class="muted small">Ask ComplianceIQ to correlate your top open findings into one systemic-risk narrative — grounded in the compliance corpus.</p>
            <button class="btn btn-primary btn-block mt" id="gen-insight" ${topOpen.length ? "" : "disabled"}>${icon("spark", 16)} Generate insight</button>
            ${topOpen.length ? "" : '<p class="hint">No open findings to correlate.</p>'}
          </div>
        </div>
      </div>`;

    // Row navigation
    root.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => ctx.navigate(`/findings/${tr.dataset.id}`)));
    root.querySelector("[data-go]")?.addEventListener("click", () => ctx.navigate("/findings"));

    // On-demand AI insight (real /correlate call)
    root.querySelector("#gen-insight")?.addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      setBusy(btn, true, "Correlating…");
      try {
        const res = await aiCorrelate(topOpen);
        qs("#ai-insight").innerHTML = `<div class="notice mb">${icon("spark", 16)}<div>Systemic-risk narrative across your ${topOpen.length} highest findings.</div></div>
          <div class="md">${mdLite(res.narrative)}</div>`;
      } catch (err) {
        setBusy(btn, false);
        toast({ title: "Insight failed", msg: err.message, kind: "err", timeout: 6000 });
      }
    });
  },
};

function prettyRule(ruleId = "") {
  return ruleId.replace(/^rule-/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function qs(sel) { return document.querySelector(sel); }
