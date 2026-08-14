// store.js — tiny in-memory app state. Holds the current tenant's findings (from
// GET /api/v1/findings) so pages share one fetch, plus memoised AI results per
// finding so re-opening a finding doesn't re-spend a model call. Cleared on
// sign-out. Deliberately minimal — no framework, just a cache with helpers.

import { listFindings } from "./api.js";
import { SEVERITY_ORDER } from "./config.js";

const state = {
  findings: null, // Finding[]
  loadedAt: 0,
  ai: new Map(), // key `${kind}:${findingId}` -> result
};

export function reset() {
  state.findings = null;
  state.loadedAt = 0;
  state.ai.clear();
}

/** Fetch (and cache) the tenant's findings. `force` bypasses the cache. */
export async function loadFindings({ force = false } = {}) {
  if (!force && state.findings && Date.now() - state.loadedAt < 60000) return state.findings;
  const page = await listFindings({ limit: 500 });
  state.findings = page.items || [];
  state.loadedAt = Date.now();
  return state.findings;
}

export function getCachedFindings() { return state.findings || []; }
export function findFinding(id) { return (state.findings || []).find((f) => f.id === id) || null; }

export function cacheAi(kind, findingId, value) { state.ai.set(`${kind}:${findingId}`, value); }
export function getAi(kind, findingId) { return state.ai.get(`${kind}:${findingId}`); }

/* ------------------------------ Aggregations ----------------------------- */
// Dashboard/risk metrics are computed client-side from the findings list, since
// the backend exposes no aggregate endpoint (documented as such in the guides).
export function computeMetrics(findings) {
  const fails = findings.filter((f) => f.status === "fail");
  const passes = findings.filter((f) => f.status === "pass");
  const bySeverity = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const f of fails) if (bySeverity[f.severity] !== undefined) bySeverity[f.severity] += 1;

  const byFramework = {};
  const byCloudFail = {};
  const byDomain = {};
  for (const f of findings) {
    byFramework[f.framework] = byFramework[f.framework] || { total: 0, fail: 0 };
    byFramework[f.framework].total += 1;
    if (f.status === "fail") byFramework[f.framework].fail += 1;
    if (f.status === "fail") byDomain[f.domain] = (byDomain[f.domain] || 0) + 1;
  }

  // A transparent, weighted compliance score: 100 minus weighted open-failure
  // penalty, normalised by resource count. Heuristic and clearly a client-side
  // summary — not a backend-computed figure.
  const weight = { critical: 10, high: 6, medium: 3, low: 1 };
  const penalty = fails.reduce((acc, f) => acc + (weight[f.severity] || 1), 0);
  const denom = Math.max(findings.length * 10, 1);
  const score = Math.max(0, Math.min(100, Math.round(100 - (penalty / denom) * 100)));

  return {
    total: findings.length,
    open: fails.length,
    resolved: passes.length,
    bySeverity,
    byFramework,
    byDomain,
    score,
    severityOrdered: SEVERITY_ORDER.map((s) => ({ key: s, count: bySeverity[s] })),
  };
}

export function severityRank(sev) { return { critical: 4, high: 3, medium: 2, low: 1 }[sev] || 0; }
