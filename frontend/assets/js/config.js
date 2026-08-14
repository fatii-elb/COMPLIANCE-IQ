// config.js — static configuration and shared constants.
// The frontend is served same-origin by the FastAPI app, so the API base is "".
// Override by setting window.CIQ_API_BASE before this module loads (e.g. to point
// a locally-served frontend at a remote backend — requires CORS on that backend).

export const API_BASE = (typeof window !== "undefined" && window.CIQ_API_BASE) || "";

export const APP = {
  name: "ComplianceIQ",
  tagline: "Grounded GRC intelligence for multi-cloud compliance",
};

// Human labels for the backend's StrEnum wire values (domain/value_objects/enums.py).
export const SEVERITY = {
  critical: { label: "Critical", cls: "sev-critical", weight: 4, color: "var(--sev-critical)" },
  high: { label: "High", cls: "sev-high", weight: 3, color: "var(--sev-high)" },
  medium: { label: "Medium", cls: "sev-medium", weight: 2, color: "var(--sev-medium)" },
  low: { label: "Low", cls: "sev-low", weight: 1, color: "var(--sev-low)" },
};
export const SEVERITY_ORDER = ["critical", "high", "medium", "low"];

export const FRAMEWORKS = {
  iso_27001: { label: "ISO 27001", short: "ISO 27001", note: "Identifiers & original summaries only (ISO copyright)." },
  loi_05_20: { label: "Loi 05-20 (Morocco)", short: "Loi 05-20", note: "Moroccan personal-data protection law. Public source." },
  dnssi: { label: "DNSSI (Morocco)", short: "DNSSI", note: "Directive Nationale de la Sécurité des Systèmes d'Information. Public source." },
  nist_csf: { label: "NIST CSF", short: "NIST CSF", note: "NIST Cybersecurity Framework." },
  soc_2: { label: "SOC 2", short: "SOC 2", note: "Trust Services Criteria." },
};

export const CLOUDS = {
  aws: { label: "AWS", color: "#ff9900" },
  azure: { label: "Azure", color: "#3ea9f5" },
  gcp: { label: "GCP", color: "#ea4335" },
};

export const DOMAINS = {
  iam: "Identity & Access",
  network: "Network",
  encryption: "Encryption",
  logging: "Logging & Monitoring",
  storage: "Storage",
};

export const STATUS = {
  pass: { label: "Pass", cls: "badge-ok" },
  fail: { label: "Fail", cls: "badge-fail" },
};

// Detect the cloud provider from a resource id / arn heuristically (display only).
export function detectCloud(resourceId = "") {
  const r = resourceId.toLowerCase();
  if (r.startsWith("arn:aws") || r.includes("aws")) return "aws";
  if (r.includes("subscriptions/") || r.includes("azure")) return "azure";
  if (r.startsWith("projects/") || r.includes("gcp") || r.includes("google")) return "gcp";
  return "aws";
}
