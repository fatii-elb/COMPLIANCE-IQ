// auth.js — client-side session. Holds the bearer token, decodes its claims for
// display, persists across reloads, and exposes sign-in/out. The token is
// verified server-side on every API call (this service only *verifies* JWTs);
// nothing here trusts the token beyond showing who you are.

import { mintDevToken, setAuthToken } from "./api.js";

const STORAGE_KEY = "ciq.session.v1";
let _session = null; // { token, sub, tenantId, roles, exp }

function decodeJwt(token) {
  try {
    const [, payloadB64] = token.split(".");
    const json = atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function sessionFromToken(token) {
  const claims = decodeJwt(token) || {};
  return {
    token,
    sub: claims.sub || "unknown",
    tenantId: claims.tenant_id || "unknown",
    roles: Array.isArray(claims.roles) ? claims.roles : [],
    exp: typeof claims.exp === "number" ? claims.exp : 0,
  };
}

/** Restore a persisted session (if any, and not expired). Call once at boot. */
export function restoreSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (s.exp && s.exp * 1000 < Date.now()) { clearSession(); return null; }
    _session = s;
    setAuthToken(s.token);
    return s;
  } catch {
    return null;
  }
}

export function getSession() { return _session; }
export function isAuthenticated() { return !!_session && (!_session.exp || _session.exp * 1000 > Date.now()); }

export function setSession(token) {
  _session = sessionFromToken(token);
  setAuthToken(token);
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(_session)); } catch { /* ignore */ }
  return _session;
}

export function clearSession() {
  _session = null;
  setAuthToken(null);
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}

/** Sign in via the LOCAL dev-token endpoint. */
export async function signInDev({ tenant_id, subject, roles, ttl_minutes }) {
  const res = await mintDevToken({ tenant_id, subject, roles, ttl_minutes });
  return setSession(res.access_token);
}

/** Sign in with a pasted, already-issued JWT (the production path). */
export function signInWithToken(token) {
  const t = (token || "").trim();
  if (t.split(".").length !== 3) throw new Error("That doesn't look like a JWT (expected three dot-separated parts).");
  return setSession(t);
}

/** Milliseconds until the token expires (or Infinity if none). */
export function msUntilExpiry() {
  if (!_session || !_session.exp) return Infinity;
  return _session.exp * 1000 - Date.now();
}
