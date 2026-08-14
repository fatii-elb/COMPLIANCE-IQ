// pages/settings.js — session details, backend connection/health, appearance,
// and sign-out. Read-only except the theme toggle and sign-out (which the user
// controls). No product settings are invented that the backend doesn't support.

import { icon } from "../icons.js";
import { getSession, clearSession, msUntilExpiry } from "../auth.js";
import { getVersion, getReadiness } from "../api.js";
import { API_BASE } from "../config.js";
import { reset as resetStore } from "../store.js";
import { esc, fmtDateTime, loadingState, copyText, toast } from "../ui.js";

export default {
  async render(root, ctx) {
    const s = getSession();
    const ms = msUntilExpiry();
    const expLabel = ms === Infinity ? "No expiry" : ms <= 0 ? "Expired" : `${Math.round(ms / 60000)} min remaining`;
    const tokenPreview = s?.token ? s.token.slice(0, 18) + "…" + s.token.slice(-8) : "—";

    root.innerHTML = `
      <div class="page-head"><div class="ph-text"><h2>Settings</h2><p>Your session, the backend connection, and appearance.</p></div></div>

      <div class="grid cols-2 mb">
        <div class="card"><div class="card-head"><h3>${icon("user", 15)} Session</h3></div><div class="card-body">
          <dl class="kv">
            <dt>User</dt><dd>${esc(s?.sub || "—")}</dd>
            <dt>Tenant</dt><dd class="mono">${esc(s?.tenantId || "—")}</dd>
            <dt>Roles</dt><dd>${(s?.roles || []).map((r) => `<span class="chip">${esc(r)}</span>`).join(" ") || "—"}</dd>
            <dt>Token</dt><dd><span class="mono tiny">${esc(tokenPreview)}</span> <button class="btn btn-sm btn-ghost" id="copy-tok">${icon("copy", 13)}</button></dd>
            <dt>Expiry</dt><dd><span class="badge ${ms > 0 || ms === Infinity ? "badge-ok" : "badge-fail"}">${esc(expLabel)}</span></dd>
          </dl>
          <div class="divider"></div>
          <button class="btn btn-danger" id="signout">${icon("logout", 16)} Sign out</button>
        </div></div>

        <div class="card"><div class="card-head"><h3>${icon("cloud", 15)} Connection</h3><div class="card-actions"><button class="btn btn-sm btn-ghost" id="refresh">${icon("refresh", 14)} Recheck</button></div></div>
          <div class="card-body">
            <dl class="kv"><dt>API base</dt><dd class="mono">${esc(API_BASE || "(same origin)")}</dd></dl>
            <div id="conn" class="mt">${loadingState("Checking backend…")}</div>
          </div></div>
      </div>

      <div class="card"><div class="card-head"><h3>${icon("settings", 15)} Appearance</h3></div><div class="card-body">
        <div class="row between"><div><div style="font-weight:600">Theme</div><div class="tiny muted">Switch between the dark and light console.</div></div>
          <div class="seg" style="width:200px;margin:0">
            <button data-theme-set="dark" class="${current() === "dark" ? "active" : ""}">Dark</button>
            <button data-theme-set="light" class="${current() === "light" ? "active" : ""}">Light</button>
          </div></div>
      </div></div>`;

    root.querySelector("#copy-tok")?.addEventListener("click", () => copyText(s?.token || ""));
    root.querySelector("#signout").addEventListener("click", () => {
      clearSession(); resetStore();
      location.hash = ""; location.reload();
    });
    root.querySelector("#refresh").addEventListener("click", () => loadConn(root));
    root.querySelectorAll("[data-theme-set]").forEach((b) => b.addEventListener("click", () => {
      setTheme(b.dataset.themeSet);
      root.querySelectorAll("[data-theme-set]").forEach((x) => x.classList.toggle("active", x === b));
      toast({ title: `${b.dataset.themeSet[0].toUpperCase()}${b.dataset.themeSet.slice(1)} theme`, kind: "ok", timeout: 1400 });
    }));

    loadConn(root);
  },
};

async function loadConn(root) {
  const box = root.querySelector("#conn");
  box.innerHTML = loadingState("Checking backend…");
  try {
    const [v, ready] = await Promise.all([getVersion(), getReadiness().catch(() => null)]);
    const comps = (ready?.components || []).map((c) => `<div class="row between small"><span>${esc(c.name)}</span><span class="badge ${c.healthy ? "badge-ok" : "badge-fail"}">${c.healthy ? "healthy" : "down"}</span></div>`).join("");
    box.innerHTML = `<dl class="kv"><dt>Service</dt><dd>${esc(v.name)}</dd><dt>Version</dt><dd>v${esc(v.version)}</dd><dt>Environment</dt><dd><span class="chip">${esc(v.environment)}</span></dd><dt>Readiness</dt><dd>${ready ? `<span class="badge ${ready.ready ? "badge-ok" : "badge-fail"}">${ready.ready ? "ready" : "not ready"}</span>` : "—"}</dd></dl>${comps ? `<div class="divider"></div><div class="tiny muted mb">Dependencies</div><div class="stack gap-sm">${comps}</div>` : ""}`;
  } catch (err) {
    box.innerHTML = `<div class="notice warn">${icon("alert", 16)}<div>Backend unreachable: ${esc(err.message)}</div></div>`;
  }
}

/* ------------------------------- Theme ----------------------------------- */
const THEME_KEY = "ciq.theme";
function current() { return document.documentElement.getAttribute("data-theme") || "dark"; }
function setTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem(THEME_KEY, t); } catch { /* ignore */ }
}
