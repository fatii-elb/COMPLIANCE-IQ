// charts.js — dependency-free inline-SVG charts. Small, readable, theme-aware
// (they use currentColor / passed colors). Return HTML strings.

import { esc } from "./ui.js";

/** A donut gauge for a 0–100 score. */
export function scoreDonut(score, { size = 168, label = "Compliance" } = {}) {
  const r = size / 2 - 14;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = score >= 80 ? "var(--ok)" : score >= 55 ? "var(--sev-medium)" : "var(--sev-critical)";
  const cx = size / 2;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${label} score ${score} percent">
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="var(--bg-2)" stroke-width="12"/>
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${color}" stroke-width="12" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - pct)}" transform="rotate(-90 ${cx} ${cx})"
      style="transition:stroke-dashoffset .8s cubic-bezier(.4,0,.2,1)"/>
    <text x="50%" y="47%" text-anchor="middle" dominant-baseline="middle" font-size="34" font-weight="720" fill="var(--text)">${score}</text>
    <text x="50%" y="63%" text-anchor="middle" font-size="12" fill="var(--muted)">out of 100</text>
  </svg>`;
}

/** A stacked severity donut from {critical,high,medium,low} counts. */
export function severityDonut(bySeverity, { size = 168 } = {}) {
  const order = [
    ["critical", "var(--sev-critical)"],
    ["high", "var(--sev-high)"],
    ["medium", "var(--sev-medium)"],
    ["low", "var(--sev-low)"],
  ];
  const total = order.reduce((a, [k]) => a + (bySeverity[k] || 0), 0);
  const r = size / 2 - 14, cx = size / 2, c = 2 * Math.PI * r;
  let offset = 0, segs = "";
  if (total === 0) {
    segs = `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="var(--bg-2)" stroke-width="14"/>`;
  } else {
    for (const [k, color] of order) {
      const val = bySeverity[k] || 0;
      if (!val) continue;
      const frac = val / total;
      const len = c * frac;
      segs += `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${color}" stroke-width="14"
        stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-offset}" transform="rotate(-90 ${cx} ${cx})"/>`;
      offset += len;
    }
  }
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="Findings by severity">
    ${segs}
    <text x="50%" y="46%" text-anchor="middle" dominant-baseline="middle" font-size="30" font-weight="720" fill="var(--text)">${total}</text>
    <text x="50%" y="62%" text-anchor="middle" font-size="11.5" fill="var(--muted)">open findings</text>
  </svg>`;
}

/** Horizontal labelled bars. rows: [{label, value, color}] scaled to max. */
export function barList(rows, { max } = {}) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return rows
    .map(
      (r) => `<div class="bar-row"><div class="truncate" title="${esc(r.label)}">${esc(r.label)}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round((r.value / top) * 100)}%;background:${r.color || "var(--brand-grad)"}"></div></div>
      <div class="bar-num">${r.value}</div></div>`
    )
    .join("");
}

/** A compact coverage bar (fail vs pass) for a framework row. */
export function coverageBar(pct, color = "var(--brand-grad)") {
  return `<div class="meter"><span style="width:${Math.max(2, Math.min(100, pct))}%;background:${color}"></span></div>`;
}
