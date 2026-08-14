// ui.js — shared rendering helpers: escaping, formatting, badges, empty/loading/
// error states, toasts, a modal, citations, and a safe markdown-lite renderer.
// Keeping these in one place is what makes the product feel consistent.

import { icon } from "./icons.js";
import { SEVERITY, STATUS, FRAMEWORKS, CLOUDS, DOMAINS, detectCloud } from "./config.js";

/* ------------------------------- DOM utils ------------------------------- */
export const qs = (sel, root = document) => root.querySelector(sel);
export const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));
export function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ------------------------------ Formatting ------------------------------- */
export function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}
export function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
export function relTime(iso) {
  const d = new Date(iso); if (isNaN(d)) return "—";
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  const units = [["yr", 31536000], ["mo", 2592000], ["d", 86400], ["h", 3600], ["m", 60]];
  for (const [u, n] of units) { if (Math.abs(s) >= n) return `${Math.round(s / n)}${u} ago`; }
  return "just now";
}
export function fmtMoney(v, currency = "MAD") {
  const n = Number(v);
  if (isNaN(n)) return "—";
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} ${currency}`;
}
export const fmtNum = (n) => Number(n || 0).toLocaleString();
export function initials(name = "") {
  const parts = name.replace(/@.*/, "").split(/[.\s_-]+/).filter(Boolean);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "U";
}

/* -------------------------------- Badges --------------------------------- */
export function severityBadge(sev) {
  const s = SEVERITY[sev] || { label: sev, cls: "badge-muted" };
  return `<span class="badge ${s.cls}"><span class="dot"></span>${esc(s.label)}</span>`;
}
export function statusBadge(st) {
  const s = STATUS[st] || { label: st, cls: "badge-muted" };
  return `<span class="badge ${s.cls}">${esc(s.label)}</span>`;
}
export function frameworkLabel(fw) { return FRAMEWORKS[fw]?.short || fw; }
export function frameworkBadge(fw) {
  return `<span class="badge badge-brand">${esc(frameworkLabel(fw))}</span>`;
}
export function cloudTag(cloud) {
  const c = CLOUDS[cloud] || { label: cloud, color: "var(--muted)" };
  return `<span class="cloud-tag" style="color:${c.color}">${icon("cloud", 14)}${esc(c.label)}</span>`;
}
export function cloudOf(finding) { return detectCloud(finding.resource_id); }
export function domainLabel(d) { return DOMAINS[d] || d; }
export function verifiedBadge(verified) {
  return verified
    ? `<span class="badge badge-verified">${icon("checkCircle", 13)} Grounded &amp; verified</span>`
    : `<span class="badge badge-unverified">${icon("alert", 13)} Not verified</span>`;
}

/* -------------------------------- States --------------------------------- */
export function loadingState(msg = "Loading…") {
  return `<div class="state"><div class="state-ico"><span class="spinner"></span></div><p>${esc(msg)}</p></div>`;
}
export function emptyState({ title = "Nothing here yet", msg = "", action = "" } = {}) {
  return `<div class="state"><div class="state-ico">${icon("inbox", 24)}</div><h3>${esc(title)}</h3>${msg ? `<p>${esc(msg)}</p>` : ""}${action}</div>`;
}
export function errorState(err, retryAttr = "") {
  const message = err?.message || "Something went wrong.";
  const cid = err?.correlationId ? `<p class="tiny muted">Reference: <span class="mono">${esc(err.correlationId)}</span></p>` : "";
  const retry = retryAttr ? `<button class="btn btn-sm" ${retryAttr}>${icon("refresh", 15)} Try again</button>` : "";
  return `<div class="state error"><div class="state-ico">${icon("alert", 24)}</div><h3>Unable to load</h3><p>${esc(message)}</p>${cid}${retry}</div>`;
}
export function skeletonRows(n = 5, cols = 5) {
  let out = "";
  for (let i = 0; i < n; i++) {
    out += "<tr>";
    for (let c = 0; c < cols; c++) out += `<td><div class="skeleton sk-line" style="width:${50 + ((i * 7 + c * 13) % 45)}%"></div></td>`;
    out += "</tr>";
  }
  return out;
}

/* -------------------------------- Toasts --------------------------------- */
export function toast({ title = "", msg = "", kind = "info", timeout = 4200 } = {}) {
  const stack = qs("#toasts");
  if (!stack) return;
  const icoName = kind === "ok" ? "checkCircle" : kind === "err" ? "xCircle" : kind === "warn" ? "alert" : "info";
  const node = h(`<div class="toast ${kind}"><span class="t-ico">${icon(icoName, 18)}</span><div><div class="t-title">${esc(title)}</div>${msg ? `<div class="t-msg">${esc(msg)}</div>` : ""}</div><button class="t-close" aria-label="Dismiss">${icon("x", 15)}</button></div>`);
  node.querySelector(".t-close").addEventListener("click", () => node.remove());
  stack.appendChild(node);
  if (timeout) setTimeout(() => node.remove(), timeout);
}

/* --------------------------------- Modal --------------------------------- */
export function openModal(innerHtml, { onMount } = {}) {
  closeModal();
  const scrim = h('<div class="scrim" id="modal-scrim"></div>');
  const wrap = h(`<div class="modal" id="modal-wrap">${innerHtml}</div>`);
  document.body.appendChild(scrim);
  document.body.appendChild(wrap);
  scrim.addEventListener("click", closeModal);
  wrap.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", closeModal));
  document.addEventListener("keydown", escClose);
  if (onMount) onMount(wrap);
  return wrap;
}
function escClose(e) { if (e.key === "Escape") closeModal(); }
export function closeModal() {
  document.getElementById("modal-scrim")?.remove();
  document.getElementById("modal-wrap")?.remove();
  document.removeEventListener("keydown", escClose);
}

/* ------------------------------- Citations ------------------------------- */
export function citationCard(c) {
  return `<div class="citation"><span class="c-ico">${icon("shield", 18)}</span><div>
    <div class="c-fw">${esc(frameworkLabel(c.framework))} · <span class="c-ctrl">${esc(c.control_id)}</span></div>
    <div class="c-ref">${esc(c.reference)}</div></div></div>`;
}
export function citationList(citations = []) {
  if (!citations.length) return `<p class="muted small">No citations.</p>`;
  return `<div class="stack gap-sm">${citations.map(citationCard).join("")}</div>`;
}

/* ----------------------------- Markdown-lite ----------------------------- */
// A deliberately small, safe renderer. Everything is HTML-escaped first, then a
// handful of patterns are upgraded. No raw HTML from model output is ever trusted.
export function mdLite(text) {
  const lines = String(text ?? "").split(/\r?\n/);
  let html = "", inUl = false, inOl = false;
  const closeLists = () => { if (inUl) { html += "</ul>"; inUl = false; } if (inOl) { html += "</ol>"; inOl = false; } };
  const inline = (s) =>
    esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { closeLists(); continue; }
    let m;
    if ((m = line.match(/^###\s+(.*)/))) { closeLists(); html += `<h4>${inline(m[1])}</h4>`; }
    else if ((m = line.match(/^##\s+(.*)/))) { closeLists(); html += `<h3>${inline(m[1])}</h3>`; }
    else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (!inUl) { closeLists(); html += "<ul>"; inUl = true; } html += `<li>${inline(m[1])}</li>`; }
    else if ((m = line.match(/^\s*\d+\.\s+(.*)/))) { if (!inOl) { closeLists(); html += "<ol>"; inOl = true; } html += `<li>${inline(m[1])}</li>`; }
    else { closeLists(); html += `<p>${inline(line)}</p>`; }
  }
  closeLists();
  return html || `<p class="muted">—</p>`;
}

/* ------------------------------- Clipboard ------------------------------- */
export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast({ title: "Copied", kind: "ok", timeout: 1600 }); }
  catch { toast({ title: "Copy failed", msg: "Select and copy manually.", kind: "warn" }); }
}
export function downloadFile(filename, content, mime = "text/plain") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click();
  a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* --------------------------- Button busy helper -------------------------- */
export function setBusy(btn, busy, busyLabel = "Working…") {
  if (!btn) return;
  if (busy) {
    btn.dataset.label = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" style="width:15px;height:15px;border-width:2px"></span> ${esc(busyLabel)}`;
  } else {
    btn.disabled = false;
    if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
  }
}
