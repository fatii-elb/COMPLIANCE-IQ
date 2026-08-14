// pages/copilot.js — the grounded compliance chat. Each question is a real call
// to POST /api/v1/ai/ask → CopilotAnswer {answer, citations, citation_verified,
// abstained}. History is kept client-side for the session. The UI makes it
// obvious when an answer is grounded, and when the copilot abstained.

import { icon } from "../icons.js";
import { aiAsk } from "../api.js";
import { esc, mdLite, citationList, verifiedBadge, toast } from "../ui.js";
import { FRAMEWORKS } from "../config.js";

const SUGGESTIONS = [
  "What does ISO 27001 require for access control?",
  "Why is an open security group a compliance risk?",
  "What are the logging obligations under Loi 05-20?",
  "How should encryption at rest be enforced for stored data?",
];

const history = []; // { role: 'user'|'ai', ... }

export default {
  async render(root, ctx) {
    root.innerHTML = `
      <div class="page-head">
        <div class="ph-text"><h2>AI Copilot</h2><p>Ask compliance questions in plain language. Answers are grounded in the ComplianceIQ corpus and cited — or the copilot abstains rather than guess.</p></div>
        <div class="ph-actions">
          <select class="select" id="scope" style="min-width:190px">
            <option value="">All frameworks</option>
            ${Object.entries(FRAMEWORKS).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("")}
          </select>
        </div>
      </div>

      <div class="card">
        <div class="card-body chat">
          <div class="chat-scroll" id="scroll"></div>
          <form class="chat-input" id="ask-form">
            <textarea class="textarea" id="q" placeholder="Ask ComplianceIQ…  (Enter to send, Shift+Enter for newline)" rows="1"></textarea>
            <button class="btn btn-primary" id="send" type="submit" style="height:46px">${icon("send", 16)} Send</button>
          </form>
        </div>
      </div>`;

    const scroll = root.querySelector("#scroll");
    const input = root.querySelector("#q");

    const paint = () => {
      if (!history.length) {
        scroll.innerHTML = welcome();
        scroll.querySelectorAll("[data-suggest]").forEach((b) => b.addEventListener("click", () => { input.value = b.dataset.suggest; input.focus(); autosize(); }));
        return;
      }
      scroll.innerHTML = history.map(renderMsg).join("");
      scroll.scrollTop = scroll.scrollHeight;
    };
    paint();

    const autosize = () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; };
    input.addEventListener("input", autosize);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); root.querySelector("#ask-form").requestSubmit(); } });

    root.querySelector("#ask-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (!q) return;
      const framework = root.querySelector("#scope").value || null;
      history.push({ role: "user", text: q, framework });
      history.push({ role: "ai", pending: true });
      input.value = ""; autosize(); paint();

      try {
        const res = await aiAsk(q, framework);
        history[history.length - 1] = { role: "ai", answer: res };
      } catch (err) {
        history[history.length - 1] = { role: "ai", error: err.message };
        toast({ title: "Copilot error", msg: err.message, kind: "err", timeout: 6000 });
      }
      paint();
    });
  },
};

function welcome() {
  return `<div class="state" style="padding:32px 20px">
    <div class="state-ico" style="background:var(--brand-grad);color:#04121f">${icon("copilot", 26)}</div>
    <h3>ComplianceIQ Copilot</h3>
    <p>Grounded answers to your compliance questions, every claim backed by a real control. Try one of these:</p>
    <div class="row wrap gap-sm" style="justify-content:center;max-width:640px;margin:0 auto">
      ${SUGGESTIONS.map((s) => `<button class="chip" data-suggest="${esc(s)}">${icon("spark", 13)} ${esc(s)}</button>`).join("")}
    </div>
  </div>`;
}

function renderMsg(m) {
  if (m.role === "user") {
    return `<div class="msg user"><div class="m-avatar">${icon("user", 16)}</div><div class="m-body">
      <div class="m-name">You${m.framework ? ` · scoped to ${esc(FRAMEWORKS[m.framework]?.short || m.framework)}` : ""}</div>
      <div class="m-bubble">${esc(m.text)}</div></div></div>`;
  }
  // AI
  let inner;
  if (m.pending) {
    inner = `<div class="m-bubble"><span class="typing"><span></span><span></span><span></span></span> <span class="muted small">Retrieving &amp; grounding…</span></div>`;
  } else if (m.error) {
    inner = `<div class="m-bubble" style="border-color:var(--danger)"><div class="row gap-sm" style="color:var(--danger)">${icon("alert", 16)} <b>Couldn't answer</b></div><p class="small muted" style="margin:6px 0 0">${esc(m.error)}</p></div>`;
  } else {
    const a = m.answer;
    const flag = a.abstained
      ? `<div class="grounded-flag badge-unverified">${icon("alert", 13)} Abstained — no confident grounding</div>`
      : `<div class="grounded-flag ${a.citation_verified ? "badge-verified" : "badge-unverified"}">${a.citation_verified ? icon("checkCircle", 13) + " Grounded &amp; verified" : icon("alert", 13) + " Answer not verified"}</div>`;
    const cites = (a.citations && a.citations.length)
      ? `<div class="mt"><div class="tiny muted mb">Sources</div>${citationList(a.citations)}</div>` : "";
    inner = `<div class="m-bubble"><div class="md">${mdLite(a.answer)}</div>${flag}${cites}</div>`;
  }
  return `<div class="msg ai"><div class="m-avatar">${icon("shield", 16)}</div><div class="m-body"><div class="m-name">ComplianceIQ Copilot</div>${inner}</div></div>`;
}
