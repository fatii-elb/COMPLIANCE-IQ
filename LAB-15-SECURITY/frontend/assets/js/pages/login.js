// pages/login.js — the authentication view. Two ways in:
//   1) Developer sign-in — mints a LOCAL test token (POST /api/v1/auth/dev-token).
//   2) Paste a token — the production path (a real Core-issued JWT).
// The service always verifies the token server-side; this screen never bypasses auth.

import { icon } from "../icons.js";
import { signInDev, signInWithToken } from "../auth.js";
import { getVersion } from "../api.js";
import { qs, esc, toast, setBusy } from "../ui.js";

const FEATURES = [
  { ico: "shield", t: "Grounded & cited", d: "Every AI claim is verified against a real control, or the copilot abstains." },
  { ico: "lock", t: "Multi-tenant by design", d: "Strict tenant isolation on every query, cache key, and log line." },
  { ico: "layers", t: "Framework-aware", d: "ISO 27001, NIST CSF, SOC 2, Loi 05-20 and DNSSI mapping." },
];

function view() {
  return `
  <div class="auth-wrap">
    <section class="auth-brandside">
      <div class="brand">
        <div class="brand-mark">${icon("shield", 22)}</div>
        <div><div class="brand-name" style="font-size:19px">Compliance<b>IQ</b></div><div class="brand-sub">Enterprise GRC Intelligence</div></div>
      </div>
      <div>
        <h1 class="auth-hero-title">Grounded compliance intelligence for the <b>multi-cloud</b> enterprise.</h1>
        <p class="dim" style="max-width:440px">Explain findings, map controls across frameworks, quantify financial exposure, and answer auditor questions — every answer cited and verifiable.</p>
        <div class="auth-features">
          ${FEATURES.map((f) => `<div class="auth-feature"><span class="af-ico">${icon(f.ico, 18)}</span><div><div class="af-t">${esc(f.t)}</div><div class="af-d">${esc(f.d)}</div></div></div>`).join("")}
        </div>
      </div>
      <div class="tiny muted">Every AI action runs through a single hardened AI Gateway — rate-limited, budgeted, injection-scanned, and cost-accounted.</div>
    </section>

    <section class="auth-formside">
      <div class="auth-card card card-body">
        <h2 style="font-size:20px">Sign in</h2>
        <p class="muted small mb">Access the ComplianceIQ console.</p>

        <div class="seg" role="tablist">
          <button class="active" data-tab="dev" role="tab">Developer sign-in</button>
          <button data-tab="token" role="tab">Paste a token</button>
        </div>

        <form id="dev-form" data-panel="dev">
          <div class="field"><label class="label" for="f-tenant">Tenant</label>
            <input class="input" id="f-tenant" value="tenant-a" autocomplete="off" /></div>
          <div class="field"><label class="label" for="f-sub">User</label>
            <input class="input" id="f-sub" value="demo.analyst@acme.example" autocomplete="off" /></div>
          <div class="field"><label class="label" for="f-role">Role</label>
            <select class="select" id="f-role">
              <option value="analyst">Analyst</option>
              <option value="auditor">Auditor</option>
              <option value="admin">Admin</option>
            </select></div>
          <button class="btn btn-primary btn-block" id="dev-submit" type="submit">${icon("key", 17)} Sign in</button>
          <p class="hint">Mints a short-lived local test token. Available in non-production environments only.</p>
        </form>

        <form id="token-form" data-panel="token" hidden>
          <div class="field"><label class="label" for="f-token">JWT bearer token</label>
            <textarea class="textarea" id="f-token" placeholder="eyJhbGciOiJIUzI1NiIs..." style="min-height:120px;font-family:var(--mono);font-size:12px"></textarea></div>
          <button class="btn btn-primary btn-block" id="token-submit" type="submit">${icon("lock", 17)} Use token</button>
          <p class="hint">Paste a token issued by the Core Service (or from <span class="mono">python -m scripts.mint_dev_token</span>).</p>
        </form>

        <div class="divider"></div>
        <div class="row between tiny muted"><span id="login-env">Checking backend…</span><a href="/docs" target="_blank" rel="noopener">API docs ${icon("external", 12)}</a></div>
      </div>
    </section>
  </div>`;
}

export default {
  render(root, ctx) {
    root.innerHTML = view();

    // Tab switching
    root.querySelectorAll("[data-tab]").forEach((btn) =>
      btn.addEventListener("click", () => {
        root.querySelectorAll("[data-tab]").forEach((b) => b.classList.toggle("active", b === btn));
        root.querySelectorAll("[data-panel]").forEach((p) => (p.hidden = p.dataset.panel !== btn.dataset.tab));
      })
    );

    // Backend status line
    getVersion()
      .then((v) => (qs("#login-env").textContent = `Backend online · ${v.environment} · v${v.version}`))
      .catch(() => (qs("#login-env").innerHTML = `<span style="color:var(--danger)">Backend unreachable — is it running?</span>`));

    // Dev sign-in
    qs("#dev-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const btn = qs("#dev-submit");
      setBusy(btn, true, "Signing in…");
      try {
        await signInDev({
          tenant_id: qs("#f-tenant").value.trim() || "tenant-a",
          subject: qs("#f-sub").value.trim() || "demo.analyst@acme.example",
          roles: [qs("#f-role").value],
          ttl_minutes: 120,
        });
        toast({ title: "Welcome", msg: "Signed in to ComplianceIQ.", kind: "ok" });
        ctx.onSignedIn();
      } catch (err) {
        setBusy(btn, false);
        toast({ title: "Sign-in failed", msg: err.message, kind: "err", timeout: 7000 });
      }
    });

    // Paste-token sign-in
    qs("#token-form").addEventListener("submit", (e) => {
      e.preventDefault();
      try {
        signInWithToken(qs("#f-token").value);
        toast({ title: "Token accepted", kind: "ok" });
        ctx.onSignedIn();
      } catch (err) {
        toast({ title: "Invalid token", msg: err.message, kind: "err", timeout: 6000 });
      }
    });
  },
};
