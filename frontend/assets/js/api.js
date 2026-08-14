// api.js — the single HTTP service layer. UI code never calls fetch directly;
// it calls these typed functions. Responsibilities: attach the bearer token,
// enforce a timeout, and normalise every failure into an ApiError with a
// client-safe message (the backend's error envelope is {error:{code,message,...}}).

import { API_BASE } from "./config.js";

let _token = null;

/** Set (or clear) the bearer token attached to authenticated requests. */
export function setAuthToken(token) {
  _token = token || null;
}

/** A normalised API failure. `kind` drives how the UI reacts. */
export class ApiError extends Error {
  constructor(message, { kind = "unknown", status = 0, code = "", correlationId = "", details = {} } = {}) {
    super(message);
    this.name = "ApiError";
    this.kind = kind; // network | timeout | auth | forbidden | notfound | validation | ratelimit | server | unknown
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
    this.details = details;
  }
}

const CLIENT_MESSAGES = {
  network: "ComplianceIQ can't reach the backend service. Check that it's running, then try again.",
  timeout: "The request took too long. The service may be busy — please try again.",
  auth: "Your session has expired or is invalid. Please sign in again.",
  forbidden: "You don't have access to this resource. It may belong to another tenant.",
  notfound: "We couldn't find what you were looking for.",
  validation: "The request was rejected as invalid. Please check the input and try again.",
  ratelimit: "You've hit the rate limit for this tenant. Please wait a moment and retry.",
  server: "ComplianceIQ hit an unexpected error. Please try again shortly.",
  unknown: "Something went wrong. Please try again.",
};

function kindForStatus(status) {
  if (status === 401) return "auth";
  if (status === 403) return "forbidden";
  if (status === 404) return "notfound";
  if (status === 422 || status === 400) return "validation";
  if (status === 429) return "ratelimit";
  if (status >= 500) return "server";
  return "unknown";
}

async function request(path, { method = "GET", body, auth = true, timeout = 45000 } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && _token) headers["Authorization"] = `Bearer ${_token}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err.name === "AbortError") throw new ApiError(CLIENT_MESSAGES.timeout, { kind: "timeout" });
    throw new ApiError(CLIENT_MESSAGES.network, { kind: "network" });
  }
  clearTimeout(timer);

  const text = await res.text();
  let payload = null;
  if (text) { try { payload = JSON.parse(text); } catch { payload = null; } }

  if (!res.ok) {
    const kind = kindForStatus(res.status);
    const env = payload && payload.error ? payload.error : {};
    throw new ApiError(env.message || CLIENT_MESSAGES[kind], {
      kind,
      status: res.status,
      code: env.code || "",
      correlationId: env.correlation_id || "",
      details: env.details || {},
    });
  }
  return payload;
}

/* --------------------------- Operational (no auth) --------------------------- */
export const getHealth = () => request("/health", { auth: false, timeout: 8000 });
export const getVersion = () => request("/version", { auth: false, timeout: 8000 });
export const getReadiness = () => request("/health/ready", { auth: false, timeout: 8000 });

/* ------------------------------ Dev sign-in ------------------------------ */
// LOCAL-only helper endpoint (see presentation/routers/dev_auth.py). Absent in
// production, where a real Core-issued token is pasted instead.
export const mintDevToken = (payload) =>
  request("/api/v1/auth/dev-token", { method: "POST", body: payload, auth: false, timeout: 8000 });

/* ------------------------------- Findings -------------------------------- */
export function listFindings({ framework, severity, status, limit = 200, offset = 0 } = {}) {
  const qs = new URLSearchParams();
  if (framework) qs.set("framework", framework);
  if (severity) qs.set("severity", severity);
  if (status) qs.set("status", status);
  qs.set("limit", String(limit));
  qs.set("offset", String(offset));
  return request(`/api/v1/findings?${qs.toString()}`);
}
export const getFinding = (id) => request(`/api/v1/findings/${encodeURIComponent(id)}`);

/* ---------------------------- AI capabilities ---------------------------- */
export const aiEnrich = (findings) => request("/api/v1/ai/enrich", { method: "POST", body: { findings } });
export const aiEnrichByIds = (finding_ids) => request("/api/v1/ai/enrich/by-ids", { method: "POST", body: { finding_ids } });
export const aiAsk = (question, framework) => request("/api/v1/ai/ask", { method: "POST", body: { question, framework: framework || null } });
export const aiRemediate = (finding) => request("/api/v1/ai/remediate", { method: "POST", body: { finding } });
export const aiCorrelate = (findings) => request("/api/v1/ai/correlate", { method: "POST", body: { findings } });
export const aiMap = (finding) => request("/api/v1/ai/map", { method: "POST", body: { finding } });
export const aiFinancial = (finding) => request("/api/v1/ai/financial", { method: "POST", body: { finding } });
export const aiReport = (findings) => request("/api/v1/ai/report", { method: "POST", body: { findings } });
