// pages/reports.js — executive compliance reporting. Generating a report is a
// two-step real pipeline:
//   1) POST /api/v1/ai/enrich   — turn findings into grounded EnrichedFindings
//   2) POST /api/v1/ai/report   — draft an executive summary over them (ReportDraft)
// PDF rendering is a backend concern that is NOT IMPLEMENTED yet; the client
// offers Markdown export and browser print as an honest interim.

import { icon } from "../icons.js";
import { loadFindings, computeMetrics } from "../store.js";
import { aiEnrich, aiReport } from "../api.js";
import {
  esc, loadingState, errorState, emptyState, mdLite, fmtDateTime,
  fmtNum, downloadFile, toast, setBusy,
} from "../ui.js";
import { barList } from "../charts.js";
import { SEVERITY } from "../config.js";

let lastReport = null;

export default {
  async render(root, ctx) {
    root.innerHTML = loadingState("Preparing report workspace…");
    let findings;
    try { findings = await loadFindings(); }
    catch (err) { root.innerHTML = errorState(err); return; }

    const fails = findings.filter((f) => f.status === "fail");
    const m = computeMetrics(findings);

    root.innerHTML = `
      <div class="page-head">
        <div class="ph-text"><h2>Reports</h2><p>Generate an executive compliance report. ComplianceIQ enriches your findings with grounded explanations, then drafts an audit-ready summary.</p></div>
        <div class="ph-actions" id="report-actions"></div>
      </div>

      <div class="grid cols-3 mb">
        <div class="card span-2">
          <div class="card-head"><h3>Report scope</h3></div>
          <div class="card-body">
            <label class="label">Findings to include</label>
            <select class="select" id="scope" style="max-width:320px">
              <option value="open">All open findings (${fails.length})</option>
              <option value="crithigh">Critical &amp; High only (${m.bySeverity.critical + m.bySeverity.high})</option>
              <option value="all">Every finding (${findings.length})</option>
            </select>
            <p class="hint">The report is grounded: each included finding is first explained and cited before the summary is drafted.</p>
            <button class="btn btn-primary mt" id="gen">${icon("report", 16)} Generate report</button>
          </div>
        </div>
        <div class="card"><div class="card-head"><h3>What's inside</h3></div><div class="card-body small stack gap-sm">
          <div class="row gap-sm">${icon("check", 15)} Executive summary</div>
          <div class="row gap-sm">${icon("check", 15)} Severity breakdown</div>
          <div class="row gap-sm">${icon("check", 15)} Finding coverage count</div>
          <div class="row gap-sm">${icon("check", 15)} Grounded, cited basis</div>
          <div class="notice mt"><span class="status-tag status-future">Future</span> Signed PDF export is a backend feature not yet implemented — Markdown &amp; print are provided.</div>
        </div></div>
      </div>

      <div id="report-out"></div>`;

    const out = root.querySelector("#report-out");

    root.querySelector("#gen").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      const scope = root.querySelector("#scope").value;
      let subset = scope === "all" ? findings : scope === "crithigh" ? fails.filter((f) => ["critical", "high"].includes(f.severity)) : fails;
      if (!subset.length) { out.innerHTML = emptyState({ title: "Nothing to report", msg: "There are no findings in the selected scope." }); return; }

      setBusy(btn, true, "Enriching findings…");
      out.innerHTML = stepper(1);
      try {
        const enriched = await aiEnrich(subset);
        setBusy(btn, true, "Drafting summary…");
        out.innerHTML = stepper(2);
        const draft = await aiReport(enriched);
        lastReport = { draft, scope, generatedFor: subset.length };
        out.innerHTML = renderReport(draft);
        mountActions(root, draft);
        toast({ title: "Report ready", kind: "ok" });
      } catch (err) {
        out.innerHTML = errorState(err);
        toast({ title: "Report failed", msg: err.message, kind: "err", timeout: 6000 });
      } finally {
        setBusy(btn, false);
      }
    });

    if (lastReport) { out.innerHTML = renderReport(lastReport.draft); mountActions(root, lastReport.draft); }
  },
};

function stepper(step) {
  const s = (n, label) => `<div class="row gap-sm"><span class="af-ico" style="width:28px;height:28px;${n < step ? "background:var(--ok-soft);color:var(--ok)" : n === step ? "" : "opacity:.4"}">${n < step ? icon("check", 15) : n === step ? '<span class="spinner" style="width:14px;height:14px;border-width:2px"></span>' : n}</span>${esc(label)}</div>`;
  return `<div class="card"><div class="card-body stack">${s(1, "Enriching findings with grounded explanations")}${s(2, "Drafting the executive summary")}</div></div>`;
}

function renderReport(d) {
  const breakdown = Object.entries(d.severity_breakdown || {}).map(([k, v]) => ({ label: SEVERITY[k]?.label || k, value: v, color: SEVERITY[k]?.color || "var(--brand)" }));
  return `<div class="card" id="report-doc">
    <div class="card-head"><div><h3>Compliance Report</h3><span class="sub">Generated ${esc(fmtDateTime(d.generated_at))} · Tenant ${esc(d.tenant_id)}</span></div><span class="badge badge-brand">${icon("shield", 13)} Grounded</span></div>
    <div class="card-body">
      <div class="grid cols-3 mb">
        <div class="card card-pad" style="background:var(--card-2)"><div class="stat-label">Findings covered</div><div class="stat-value" style="font-size:26px">${fmtNum(d.finding_count)}</div></div>
        <div class="card card-pad span-2" style="background:var(--card-2)"><div class="stat-label mb">Severity breakdown</div>${breakdown.length ? barList(breakdown) : '<p class="muted small">—</p>'}</div>
      </div>
      <h3 style="font-size:16px;margin-bottom:8px">Executive summary</h3>
      <div class="md">${mdLite(d.executive_summary)}</div>
    </div>
  </div>`;
}

function mountActions(root, draft) {
  const bar = root.querySelector("#report-actions");
  bar.innerHTML = `<button class="btn btn-ghost" id="dl-md">${icon("download", 16)} Markdown</button><button class="btn btn-ghost" id="print">${icon("print", 16)} Print</button>`;
  bar.querySelector("#dl-md").addEventListener("click", () => downloadFile(`complianceiq-report-${draft.tenant_id}.md`, toMarkdown(draft), "text/markdown"));
  bar.querySelector("#print").addEventListener("click", () => window.print());
}

function toMarkdown(d) {
  const sev = Object.entries(d.severity_breakdown || {}).map(([k, v]) => `- ${k}: ${v}`).join("\n") || "- (none)";
  return `# ComplianceIQ — Compliance Report

**Tenant:** ${d.tenant_id}
**Generated:** ${fmtDateTime(d.generated_at)}
**Findings covered:** ${d.finding_count}

## Severity breakdown
${sev}

## Executive summary
${d.executive_summary}

---
*Generated by ComplianceIQ. Every included finding is grounded in cited compliance sources.*
`;
}
