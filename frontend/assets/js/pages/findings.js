// pages/findings.js — the findings management table. Loads the tenant's findings
// once (store) and applies search / filter / sort client-side for responsiveness.
// The backend also supports server-side filters (GET /api/v1/findings?severity=…),
// used on first load; see the architecture doc.

import { icon } from "../icons.js";
import { loadFindings } from "../store.js";
import {
  esc, loadingState, errorState, emptyState, severityBadge, statusBadge,
  frameworkLabel, cloudOf, cloudTag, fmtDate, toast,
} from "../ui.js";
import { FRAMEWORKS, SEVERITY, STATUS, DOMAINS } from "../config.js";
import { severityRank } from "../store.js";

const state = { q: "", framework: "", severity: "", status: "", sort: "severity", dir: -1 };

export default {
  async render(root, ctx) {
    root.innerHTML = loadingState("Loading findings…");
    let all;
    try {
      all = await loadFindings();
    } catch (err) {
      root.innerHTML = errorState(err, 'data-retry="1"');
      root.querySelector("[data-retry]")?.addEventListener("click", () => this.render(root, ctx));
      return;
    }
    ctx.setNavBadge("findings", all.length);

    root.innerHTML = `
      <div class="page-head">
        <div class="ph-text"><h2>Findings</h2><p>Every compliance verdict across your multi-cloud estate. Search, filter, and open a finding for AI explanation, mapping, remediation, and exposure.</p></div>
        <div class="ph-actions"><button class="btn btn-ghost" id="refresh">${icon("refresh", 16)} Refresh</button></div>
      </div>

      <div class="card mb">
        <div class="card-body">
          <div class="input-group">
            <div style="position:relative;flex:2;min-width:200px">
              <span style="position:absolute;left:11px;top:50%;transform:translateY(-50%);color:var(--muted)">${icon("search", 16)}</span>
              <input class="input" id="q" placeholder="Search resource, rule, control…" style="padding-left:34px" value="${esc(state.q)}">
            </div>
            <select class="select" id="framework"><option value="">All frameworks</option>${Object.entries(FRAMEWORKS).map(([k, v]) => `<option value="${k}" ${state.framework === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select>
            <select class="select" id="severity"><option value="">All severities</option>${Object.entries(SEVERITY).map(([k, v]) => `<option value="${k}" ${state.severity === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select>
            <select class="select" id="status"><option value="">Any status</option>${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${state.status === k ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select>
            <button class="btn btn-ghost" id="reset">Reset</button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-head"><h3 id="result-count"></h3></div>
        <div class="table-wrap" id="table-wrap"></div>
      </div>`;

    const rerender = () => {
      const rows = applyFilters(all);
      qs("#result-count").innerHTML = `${rows.length} of ${all.length} findings`;
      qs("#table-wrap").innerHTML = rows.length ? tableHtml(rows) : emptyState({ title: "No matching findings", msg: "Try clearing filters or adjusting your search." });
      qs("#table-wrap").querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => ctx.navigate(`/findings/${tr.dataset.id}`)));
      qs("#table-wrap").querySelectorAll("th[data-sort]").forEach((th) => th.addEventListener("click", () => {
        const key = th.dataset.sort;
        if (state.sort === key) state.dir *= -1; else { state.sort = key; state.dir = key === "detected_at" ? -1 : 1; }
        rerender();
      }));
    };

    qs("#q").addEventListener("input", (e) => { state.q = e.target.value; rerender(); });
    ["framework", "severity", "status"].forEach((id) => qs("#" + id).addEventListener("change", (e) => { state[id] = e.target.value; rerender(); }));
    qs("#reset").addEventListener("click", () => { Object.assign(state, { q: "", framework: "", severity: "", status: "" }); qs("#q").value = ""; ["framework", "severity", "status"].forEach((id) => (qs("#" + id).value = "")); rerender(); });
    qs("#refresh").addEventListener("click", async (e) => {
      const b = e.currentTarget; b.disabled = true;
      try { all = await loadFindings({ force: true }); toast({ title: "Refreshed", kind: "ok", timeout: 1500 }); rerender(); }
      catch (err) { toast({ title: "Refresh failed", msg: err.message, kind: "err" }); }
      finally { b.disabled = false; }
    });

    rerender();
  },
};

function applyFilters(all) {
  const q = state.q.trim().toLowerCase();
  let rows = all.filter((f) => {
    if (state.framework && f.framework !== state.framework) return false;
    if (state.severity && f.severity !== state.severity) return false;
    if (state.status && f.status !== state.status) return false;
    if (q) {
      const hay = `${f.resource_id} ${f.rule_id} ${f.control_id} ${f.id} ${f.domain}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const dir = state.dir;
  rows.sort((a, b) => {
    let av, bv;
    switch (state.sort) {
      case "severity": av = severityRank(a.severity); bv = severityRank(b.severity); break;
      case "detected_at": av = new Date(a.detected_at); bv = new Date(b.detected_at); break;
      default: av = String(a[state.sort] ?? ""); bv = String(b[state.sort] ?? "");
    }
    return av < bv ? -dir : av > bv ? dir : 0;
  });
  return rows;
}

function caret(key) { return state.sort === key ? `<span class="sort-caret">${state.dir > 0 ? "▲" : "▼"}</span>` : ""; }

function tableHtml(rows) {
  return `<table class="data">
    <thead><tr>
      <th data-sort="resource_id">Finding ${caret("resource_id")}</th>
      <th data-sort="severity">Severity ${caret("severity")}</th>
      <th class="no-sort">Cloud</th>
      <th data-sort="framework">Framework ${caret("framework")}</th>
      <th data-sort="domain">Domain ${caret("domain")}</th>
      <th data-sort="status">Status ${caret("status")}</th>
      <th data-sort="detected_at">Detected ${caret("detected_at")}</th>
    </tr></thead>
    <tbody>${rows.map((f) => `<tr data-id="${esc(f.id)}">
      <td><div style="font-weight:600">${esc(prettyRule(f.rule_id))}</div><div class="tiny muted mono truncate">${esc(f.resource_id)}</div></td>
      <td>${severityBadge(f.severity)}</td>
      <td>${cloudTag(cloudOf(f))}</td>
      <td><span class="tiny">${esc(frameworkLabel(f.framework))}</span><div class="tiny muted mono">${esc(f.control_id)}</div></td>
      <td class="tiny">${esc(DOMAINS[f.domain] || f.domain)}</td>
      <td>${statusBadge(f.status)}</td>
      <td class="tiny muted">${esc(fmtDate(f.detected_at))}</td>
    </tr>`).join("")}</tbody></table>`;
}

function prettyRule(ruleId = "") { return ruleId.replace(/^rule-/, "").replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function qs(sel) { return document.querySelector(sel); }
