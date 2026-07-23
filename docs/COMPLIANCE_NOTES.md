# Compliance & Copyright Notes

This document records the legal/compliance constraints that shape the knowledge
base and data handling. It backs non-negotiable rules 6 and 7.

## ISO/IEC standard text is copyrighted — enforced ingestion policy

The full text of ISO/IEC standards (e.g. ISO/IEC 27001) is **copyrighted** and
must **not** be stored or served verbatim by this system. This is a hard rule,
enforced at ingestion time (Phase 3), not a guideline.

**What we store for ISO frameworks:**
- Control **identifiers** (e.g. the clause/control reference).
- **Original summaries** written by us, in our own words.
- **References** pointing to the official source a licensed user can consult.

**What we never store:** the verbatim normative text of the standard.

The `Framework.ISO_27001` value exists as an identifier for mapping and
structure; retrieval for ISO controls returns our summaries and identifiers,
never quoted standard text.

## Primary quotable material — public sources

- **Loi 05-20** (Morocco — cybersecurity law) and **DNSSI** directives are
  public regulatory sources and are the **primary quotable material** for
  grounded citations.
- **NIST CSF** and **OWASP/MITRE ATT&CK** are publicly available and citable per
  their terms.

## Data-protection posture (RGPD / Loi 09-08)

- **Tenant isolation** is absolute (rule 1): every query, cache key, log line,
  and storage write is tenant-scoped.
- **Audit trail** (rule 7): AI decisions, retrievals, and sensitive actions are
  logged with correlation ID, tenant, model, prompt hash, token counts, and
  latency — never raw secrets or full customer payloads.
- **Secret hygiene** (rule 5): secrets come from the environment, are typed as
  `SecretStr`, and are never logged.

## Remediation safety (rules 2 & 8)

This service **proposes** Infrastructure-as-Code remediation but **never applies
it**. `RemediationProposal.approved` is structurally forced to `False`, and no
code path executes Terraform or calls a cloud mutation API. No red-team or
exploitation capability is implemented.
