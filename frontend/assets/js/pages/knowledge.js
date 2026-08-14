// pages/knowledge.js — the knowledge base. The backend indexes a compliance
// corpus and retrieves from it internally, but exposes no endpoint to *browse*
// raw documents — so this page offers grounded lookup (which runs the same RAG
// pipeline via POST /api/v1/ai/ask) and is explicit that raw browsing is not yet
// implemented.

import { icon } from "../icons.js";
import { aiAsk } from "../api.js";
import { esc, mdLite, citationList, verifiedBadge, loadingState, errorState, setBusy, toast } from "../ui.js";
import { FRAMEWORKS } from "../config.js";

export default {
  async render(root, ctx) {
    root.innerHTML = `
      <div class="page-head"><div class="ph-text"><h2>Knowledge Base</h2><p>The grounded compliance corpus behind every ComplianceIQ answer. Look up a requirement and see exactly which controls back the result.</p></div></div>

      <div class="grid cols-3 mb">
        <div class="card span-2"><div class="card-head"><h3>How grounding works</h3></div><div class="card-body">
          <p class="small">Every AI answer is retrieved from this corpus using a hybrid pipeline — semantic + keyword search, reciprocal-rank fusion, reranking, and diversity selection — then <b>verified</b>: a claim is only trusted if its cited control was actually found in the retrieved context. If nothing relevant is found, ComplianceIQ <b>abstains</b> rather than guess.</p>
          <div class="row wrap gap-sm mt">
            <span class="chip">${icon("check", 13)} Hybrid retrieval</span>
            <span class="chip">${icon("check", 13)} Reranking + MMR</span>
            <span class="chip">${icon("check", 13)} Citation verification</span>
            <span class="chip">${icon("check", 13)} Abstention on low confidence</span>
          </div>
        </div></div>
        <div class="card"><div class="card-head"><h3>Corpus coverage</h3></div><div class="card-body stack gap-sm">
          ${Object.values(FRAMEWORKS).map((v) => `<div class="row gap-sm"><span class="af-ico" style="width:26px;height:26px">${icon("book", 14)}</span><div class="small"><div style="font-weight:600">${esc(v.short)}</div><div class="tiny muted">${esc(v.note)}</div></div></div>`).join("")}
        </div></div>
      </div>

      <div class="card mb">
        <div class="card-head"><h3>${icon("search", 15)} Grounded lookup</h3><span class="sub">Runs the full retrieval + grounding pipeline</span></div>
        <div class="card-body">
          <div class="input-group">
            <input class="input" id="kq" placeholder="e.g. What controls cover encryption at rest?" style="flex:3">
            <select class="select" id="kfw"><option value="">All frameworks</option>${Object.entries(FRAMEWORKS).map(([k, v]) => `<option value="${k}">${esc(v.short)}</option>`).join("")}</select>
            <button class="btn btn-primary" id="kbtn">${icon("search", 16)} Look up</button>
          </div>
          <div id="kout" class="mt"></div>
        </div>
      </div>

      <div class="notice warn">${icon("info", 16)}<div><span class="status-tag status-future">Not implemented</span> Browsing and downloading raw corpus documents is not exposed by the backend yet. Retrieval is available today only through grounded answers (above) and the Copilot.</div></div>`;

    const run = async () => {
      const q = root.querySelector("#kq").value.trim();
      if (!q) { toast({ title: "Enter a question", kind: "warn", timeout: 2000 }); return; }
      const fw = root.querySelector("#kfw").value || null;
      const btn = root.querySelector("#kbtn");
      const box = root.querySelector("#kout");
      box.innerHTML = loadingState("Retrieving from the corpus…");
      setBusy(btn, true, "Looking up…");
      try {
        const a = await aiAsk(q, fw);
        box.innerHTML = a.abstained
          ? `<div class="notice warn">${icon("alert", 16)}<div><b>No confident match.</b> The corpus didn't contain enough relevant material, so ComplianceIQ abstained.</div></div>`
          : `<div class="card card-pad" style="background:var(--card-2)"><div class="mb">${verifiedBadge(a.citation_verified)}</div><div class="md">${mdLite(a.answer)}</div><div class="divider"></div><div class="tiny muted mb">Sources</div>${citationList(a.citations)}</div>`;
      } catch (err) { box.innerHTML = errorState(err); toast({ title: "Lookup failed", msg: err.message, kind: "err" }); }
      finally { setBusy(btn, false); }
    };
    root.querySelector("#kbtn").addEventListener("click", run);
    root.querySelector("#kq").addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  },
};
