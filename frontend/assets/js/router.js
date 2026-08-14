// router.js — a minimal hash router. Routes are patterns like "/findings/:id".
// The app registers routes; navigate() changes the hash; onChange resolves the
// match and invokes the handler with {params, query}.

const routes = [];
let notFoundHandler = null;
let onNavigate = null;

export function register(pattern, handler, meta = {}) {
  const keys = [];
  const rx = new RegExp(
    "^" + pattern.replace(/:[^/]+/g, (m) => { keys.push(m.slice(1)); return "([^/]+)"; }) + "$"
  );
  routes.push({ pattern, rx, keys, handler, meta });
}
export function setNotFound(handler) { notFoundHandler = handler; }
export function setOnNavigate(fn) { onNavigate = fn; }

export function currentPath() {
  const raw = location.hash.replace(/^#/, "") || "/";
  return raw.split("?")[0] || "/";
}
function currentQuery() {
  const raw = location.hash.replace(/^#/, "");
  const qi = raw.indexOf("?");
  return qi === -1 ? {} : Object.fromEntries(new URLSearchParams(raw.slice(qi + 1)));
}

export function navigate(path) {
  if (("#" + path) === location.hash) { resolve(); return; }
  location.hash = path;
}

function resolve() {
  const path = currentPath();
  const query = currentQuery();
  for (const r of routes) {
    const m = path.match(r.rx);
    if (m) {
      const params = {};
      r.keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));
      if (onNavigate) onNavigate({ path, route: r, params, query });
      r.handler({ params, query });
      return;
    }
  }
  if (notFoundHandler) notFoundHandler({ path });
}

export function start() {
  window.addEventListener("hashchange", resolve);
  resolve();
}
