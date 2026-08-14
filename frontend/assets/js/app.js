// app.js — application bootstrap and the authenticated shell (sidebar, topbar,
// routing). Unauthenticated users get the login view; everything else renders
// inside the shell's content area.

import { APP } from "./config.js";
import { icon } from "./icons.js";
import { restoreSession, getSession, isAuthenticated, clearSession, msUntilExpiry } from "./auth.js";
import * as router from "./router.js";
import { getHealth, getVersion } from "./api.js";
import { qs, h, esc, initials, toast } from "./ui.js";
import { reset as resetStore } from "./store.js";

import loginPage from "./pages/login.js";
import dashboardPage from "./pages/dashboard.js";
import findingsPage from "./pages/findings.js";
import findingDetailPage from "./pages/finding.js";
import copilotPage from "./pages/copilot.js";
import riskPage from "./pages/risk.js";
import reportsPage from "./pages/reports.js";
import frameworksPage from "./pages/frameworks.js";
import knowledgePage from "./pages/knowledge.js";
import settingsPage from "./pages/settings.js";

const NAV = [
  { section: "Overview" },
  { path: "/", label: "Dashboard", ico: "dashboard", page: dashboardPage },
  { section: "Compliance" },
  { path: "/findings", label: "Findings", ico: "findings", page: findingsPage, badge: "findings" },
  { path: "/frameworks", label: "Frameworks & Controls", ico: "layers", page: frameworksPage },
  { section: "Intelligence" },
  { path: "/copilot", label: "AI Copilot", ico: "copilot", page: copilotPage },
  { path: "/risk", label: "Risk Analysis", ico: "risk", page: riskPage },
  { path: "/reports", label: "Reports", ico: "report", page: reportsPage },
  { section: "Knowledge" },
  { path: "/knowledge", label: "Knowledge Base", ico: "book", page: knowledgePage },
];

// Routes that render inside the shell.
const ROUTES = [
  { path: "/", page: dashboardPage, title: "Dashboard", sub: "Compliance posture at a glance" },
  { path: "/findings", page: findingsPage, title: "Findings", sub: "Compliance findings across your cloud estate" },
  { path: "/findings/:id", page: findingDetailPage, title: "Finding", sub: "" },
  { path: "/frameworks", page: frameworksPage, title: "Frameworks & Controls", sub: "Coverage and cross-framework mapping" },
  { path: "/copilot", page: copilotPage, title: "AI Copilot", sub: "Grounded answers to compliance questions" },
  { path: "/risk", page: riskPage, title: "Risk Analysis", sub: "Systemic risk and financial exposure" },
  { path: "/reports", page: reportsPage, title: "Reports", sub: "Executive compliance reporting" },
  { path: "/knowledge", page: knowledgePage, title: "Knowledge Base", sub: "The grounded compliance corpus" },
  { path: "/settings", page: settingsPage, title: "Settings", sub: "Session, connection, and preferences" },
];

let expiryTimer = null;

/* ------------------------------- Rendering ------------------------------- */
function renderShell() {
  const s = getSession();
  const navHtml = NAV.map((n) =>
    n.section
      ? `<div class="nav-section">${esc(n.section)}</div>`
      : `<button class="nav-item" data-nav="${n.path}"><span class="nav-ico">${icon(n.ico)}</span>${esc(n.label)}${n.badge ? `<span class="nav-badge" id="badge-${n.badge}" hidden></span>` : ""}</button>`
  ).join("");

  const app = qs("#app");
  app.className = "";
  app.innerHTML = `
    <div class="drawer-scrim" id="drawer-scrim"></div>
    <div class="shell">
      <aside class="sidebar" id="sidebar">
        <div class="brand">
          <div class="brand-mark">${icon("shield", 20)}</div>
          <div><div class="brand-name">Compliance<b>IQ</b></div><div class="brand-sub">GRC Intelligence</div></div>
        </div>
        <nav class="nav">${navHtml}</nav>
        <div class="sidebar-foot">
          <div class="row between"><span>Tenant</span><span class="mono" style="color:var(--text-dim)">${esc(s?.tenantId || "—")}</span></div>
        </div>
      </aside>
      <div class="main">
        <header class="topbar">
          <button class="hamburger" id="hamburger" aria-label="Menu">${icon("menu", 22)}</button>
          <div class="crumb"><h1 id="crumb-title">Dashboard</h1><span class="crumb-sub" id="crumb-sub"></span></div>
          <div class="topbar-spacer"></div>
          <span class="env-pill" id="env-pill" title="Backend status"><span class="env-dot" id="env-dot"></span><span id="env-text">checking…</span></span>
          <button class="user-chip" id="user-chip">
            <span class="avatar">${esc(initials(s?.sub || "User"))}</span>
            <span class="u-meta"><span class="u-name">${esc((s?.sub || "user").replace(/@.*/, ""))}</span><span class="u-sub">${esc((s?.roles || []).join(", ") || "no roles")}</span></span>
            ${icon("chevronDown", 16)}
          </button>
        </header>
        <main class="content" id="view"></main>
      </div>
    </div>`;

  // Wire shell interactions
  app.querySelectorAll("[data-nav]").forEach((b) =>
    b.addEventListener("click", () => { router.navigate(b.dataset.nav); closeDrawer(); })
  );
  qs("#hamburger").addEventListener("click", toggleDrawer);
  qs("#drawer-scrim").addEventListener("click", closeDrawer);
  qs("#user-chip").addEventListener("click", openUserMenu);

  refreshEnvPill();
}

function setActiveNav(path) {
  qsAllNav().forEach((b) => {
    const p = b.dataset.nav;
    const active = p === path || (p !== "/" && path.startsWith(p));
    b.classList.toggle("active", p === "/" ? path === "/" : active);
  });
}
const qsAllNav = () => Array.from(document.querySelectorAll("[data-nav]"));

export function setNavBadge(key, value) {
  const el = document.getElementById(`badge-${key}`);
  if (!el) return;
  if (value == null) { el.hidden = true; return; }
  el.hidden = false; el.textContent = value;
}

function setCrumb(title, sub = "") {
  const t = qs("#crumb-title"), su = qs("#crumb-sub");
  if (t) t.textContent = title;
  if (su) su.textContent = sub;
  document.title = `${title} · ${APP.name}`;
}

/* ------------------------------ Drawer (mobile) -------------------------- */
function toggleDrawer() { qs("#sidebar")?.classList.toggle("open"); qs("#drawer-scrim")?.classList.toggle("show"); }
function closeDrawer() { qs("#sidebar")?.classList.remove("open"); qs("#drawer-scrim")?.classList.remove("show"); }

/* ------------------------------ User menu -------------------------------- */
function openUserMenu() {
  const existing = document.getElementById("user-menu");
  if (existing) { existing.remove(); return; }
  const s = getSession();
  const menu = h(`<div id="user-menu" class="card" style="position:fixed;top:56px;right:22px;z-index:70;width:240px;box-shadow:var(--shadow-pop);padding:8px">
    <div class="card-pad" style="padding:10px 12px;border-bottom:1px solid var(--border)">
      <div style="font-weight:650">${esc((s?.sub || "user"))}</div>
      <div class="tiny muted">Tenant: <span class="mono">${esc(s?.tenantId || "—")}</span></div>
    </div>
    <button class="nav-item" data-act="settings">${icon("settings", 17)} Settings</button>
    <button class="nav-item" data-act="signout" style="color:#fca5a5">${icon("logout", 17)} Sign out</button>
  </div>`);
  document.body.appendChild(menu);
  const close = (e) => { if (!menu.contains(e.target) && e.target.id !== "user-chip") { menu.remove(); document.removeEventListener("click", close); } };
  setTimeout(() => document.addEventListener("click", close), 0);
  menu.querySelector('[data-act="settings"]').addEventListener("click", () => { menu.remove(); router.navigate("/settings"); });
  menu.querySelector('[data-act="signout"]').addEventListener("click", signOut);
}

export function signOut() {
  clearSession();
  resetStore();
  if (expiryTimer) clearInterval(expiryTimer);
  toast({ title: "Signed out", kind: "info", timeout: 2000 });
  boot();
}

/* ------------------------------ Env pill --------------------------------- */
async function refreshEnvPill() {
  const dot = qs("#env-dot"), text = qs("#env-text");
  if (!dot) return;
  try {
    const [health, version] = await Promise.all([getHealth(), getVersion().catch(() => null)]);
    dot.classList.remove("bad");
    text.textContent = version ? `${version.environment} · v${version.version}` : `online`;
    qs("#env-pill").title = `Backend healthy (status: ${health.status})`;
  } catch {
    dot.classList.add("bad");
    text.textContent = "offline";
    qs("#env-pill").title = "Backend unreachable";
  }
}

/* ------------------------------ Expiry watch ----------------------------- */
function watchExpiry() {
  if (expiryTimer) clearInterval(expiryTimer);
  expiryTimer = setInterval(() => {
    if (!isAuthenticated()) {
      clearInterval(expiryTimer);
      toast({ title: "Session expired", msg: "Please sign in again.", kind: "warn", timeout: 6000 });
      boot();
    }
  }, 15000);
}

/* -------------------------------- Routing -------------------------------- */
function mountRoutes() {
  ROUTES.forEach((r) => {
    router.register(r.path, async ({ params, query }) => {
      if (!isAuthenticated()) { boot(); return; }
      const view = qs("#view");
      if (!view) { renderShell(); }
      const mount = qs("#view");
      setActiveNav(router.currentPath());
      setCrumb(r.title, r.sub);
      mount.innerHTML = "";
      try {
        await r.page.render(mount, { params, query, setCrumb, setNavBadge, navigate: router.navigate });
      } catch (err) {
        console.error(err);
        mount.innerHTML = `<div class="state error"><div class="state-ico">${icon("alert", 24)}</div><h3>This page failed to render</h3><p>${esc(err.message || "Unexpected error")}</p></div>`;
      }
    });
  });
  router.setNotFound(() => router.navigate("/"));
}

/* --------------------------------- Boot ---------------------------------- */
let routesMounted = false;

export function boot() {
  if (!isAuthenticated()) {
    const app = qs("#app");
    app.className = "";
    app.innerHTML = "";
    loginPage.render(app, { onSignedIn: boot });
    return;
  }
  renderShell();
  watchExpiry();
  if (!routesMounted) {
    mountRoutes();
    routesMounted = true;
    router.start(); // resolves the current hash (defaults to "/")
  } else {
    router.navigate(router.currentPath());
  }
}

/* Initialise */
try {
  const savedTheme = localStorage.getItem("ciq.theme");
  if (savedTheme) document.documentElement.setAttribute("data-theme", savedTheme);
} catch { /* ignore */ }
restoreSession();
boot();

// Expose a tiny surface for pages that need to nudge the shell.
export { router };
