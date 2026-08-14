// pages/frameworks.js — the framework catalogue with live coverage (from the
// findings list) and the cross-framework control-mapping tool (POST /api/v1/ai/map).

import { icon } from "../icons.js";
import { loadFindings, computeMetrics } from "../store.js";
import { aiMap } from "../api.js";
import {
  esc, loadingState, errorState, mdLite, frameworkLabel, citationList,
  verifiedBadge, setBusy, toast,
} from "../ui.js";
import { coverageBar } from "../charts.js";
import { FRAMEWORKS } from "../config.js";

export default {
  async render(root, ctx) {
    root.innerHTML = loadingState("Loading frameworks…");
    let findings;
    try { findings = await loadFindings(); }
    catch (err) { root.innerHTML = errorState(err); return; }
    const m = computeMetrics(findings);
    const fails = findings.filter((f) => f.status === "fail");

    const cards = Object.entries(FRAMEWORKS).map(([k, v]) => {
      const cov = m.byFramework[k] || { total: 0, fail: 0 };
      const pass = cov.total - cov.fail;
      const pct = cov.total ? Math.round((pass / cov.total) * 100) : 0;
      const color = pct >= 80 ? "var(--ok)" : pct >= 50 ? "var(--sev-medium)" : "var(--sev-critical)";
      return `<div class="card"><div class="card-body">
        <div class="row between mb"><div class="row gap-sm"><span class="af-ico">${icon("layers", 17)}</span><div><div style="font-weight:650">${esc(v.label)}</div><div class="tiny muted">${cov.total} checks · ${cov.fail} open</div></div></div>
          <span class="badge ${pct >= 80 ? "badge-ok" : pct >= 50 ? "badge-unverified" : "badge-fail"}">${pct}%</span></div>
        ${coverageBar(pct, color)}
        <p class="tiny muted mt">${esc(v.note)}</p>
      </div></div>`;
    }).join("");

    root.innerHTML = `
      <div class="page-head"><div class="ph-text"><h2>Frameworks &amp; Controls</h2><p>Coverage across the frameworks ComplianceIQ understands, and a tool to map a finding's control to its equivalents in other frameworks.</p></div></div>

      <div class="grid cols-3 mb">${cards}</div>

      <div class="notice mb">${icon("info", 16)}<div>Per ISO copyright policy, verbatim ISO 27001 text is never stored — the knowledge base holds control identifiers and original summaries. Loi 05-20 and DNSSI are public sources and are quotable.</div></div>

      <div class="card">
        <div class="card-head"><h3>${icon("map", 15)} Cross-framework control mapping</h3></div>
        <div class="card-body">
          <label class="label">Pick a finding to map its control</label>
          <div class="input-group">
            <select class="select" id="map-sel">${findings.map((f) => `<option value="${esc(f.id)}">${esc(prettyRule(f.rule_id))} — ${frameworkLabel(f.framework)} ${esc(f.control_id)}</option>`).join("")}</select>
            <button class="btn btn-primary" id="map-btn">${icon("map", 16)} Map control</button>
          </div>
          <div id="map-out" class="mt"></div>
        </div>
      </div>`;

    root.querySelector("#map-btn").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      const id = root.querySelector("#map-sel").value;
      const f = findings.find((x) => x.id === id);
      if (!f) return;
      const box = root.querySelector("#map-out");
      box.innerHTML = loadingState("Mapping control across frameworks…");
      setBusy(btn, true, "Mapping…");
      try {
        const mp = await aiMap(f);
        const rows = (mp.mappings || []).map((mc) => `<tr><td>${esc(frameworkLabel(mc.framework))}</td><td class="mono">${esc(mc.control_id)}</td><td class="tiny muted">${esc(mc.reference)}</td></tr>`).join("");
        box.innerHTML = `<div class="mb">${verifiedBadge(mp.citation_verified)}</div>
          <div class="md mb">${mdLite(mp.summary)}</div>
          ${rows ? `<div class="table-wrap"><table class="data" style="min-width:520px"><thead><tr><th>Framework</th><th>Equivalent control</th><th>Reference</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="muted small">No equivalent controls were confidently mapped for this finding.</p>'}
          <div class="divider"></div><div class="tiny muted mb">Sources</div>${citationList(mp.citations)}`;
      } catch (err) { box.innerHTML = errorState(err); toast({ title: "Mapping failed", msg: err.message, kind: "err" }); }
      finally { setBusy(btn, false); }
    });
  },
};

function prettyRule(r = "") { return r.replace(/^rule-/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
