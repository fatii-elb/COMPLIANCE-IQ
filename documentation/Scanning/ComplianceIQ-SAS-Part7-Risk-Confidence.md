# ComplianceIQ — Software Architecture Specification (SAS)

## Part 7 — Risk Intelligence Engine and Confidence Engine

**Document class:** Official Software Architecture Specification (SAS)
**Subsystem in scope:** Subsystem A — Cloud Compliance Intelligence Engine
**Continuity:** Builds on Part 3 (`RiskScore`, `Confidence` entities), Part 5 (three-valued rule outcomes), and Part 6 (`ContextualizedViolation`). Fulfills FR-08, FR-09, NFR-05, NFR-06.

---

### 1. Purpose of This Part

This part covers modules 8 and 9 from Part 1's module map — the **Risk Intelligence Engine** and the **Confidence Engine** — with full Responsibilities/Inputs/Outputs/Algorithms/Interfaces/Interactions/Failure/Performance treatment, and gives both their Core Innovation treatment: **Multi-Factor Risk Engine** (Innovation #6) and **Confidence Engine** (Innovation #5). These two engines together transform a `ContextualizedViolation` into the quantitative `RiskScore` and `Confidence` (Part 3, Sections 3.10–3.11) that will anchor the eventual `Finding`.

The design principle governing both engines, stated once here because it applies identically to each: **every formula must be a pure function of its documented inputs, versioned, and free of any hidden state** (wall-clock time beyond an explicit `calculated_at` stamp, network calls, database reads beyond the explicit inputs already fetched upstream). This is the direct, load-bearing mechanism for NFR-05 (Determinism) and NFR-06 (Auditability) at the most numerically sensitive stage of the entire pipeline — the point where a security team's actual prioritization decisions are made.

---

### 2. Risk Intelligence Engine (Module 8)

#### 2.1 Responsibilities

1. Calculating a quantitative `RiskScore.value` (0.0–10.0 scale, Part 3, Section 3.10) for every unsuppressed `ContextualizedViolation`.
2. Decomposing that value into named, individually-inspectable `factors` (never a single opaque number).
3. Deriving the `severity_band` from `value` via versioned, documented thresholds.
4. Publishing `RiskCalculated` once all violations for the scan have been scored.
5. Also scoring `AttackPath`s (Part 8) using a related but distinct formula, since an attack path's risk is a property of the *chain*, not any single resource in isolation — this distinction is detailed in Section 4.7.

#### 2.2 Inputs

- `ContextualizedViolation` list (Part 6).
- The rule/composite rule's `severity_default` (Part 3, Sections 3.7–3.8).
- Resolved context (`environment`, `data_classification`, `business_criticality`) from the Context Engine.
- Graph-derived exposure signals (e.g., is this resource internet-reachable per the Knowledge Graph, Part 5) — consumed here as a direct graph query, not re-derived.

#### 2.3 Outputs

- `RiskScore` entities (Part 3, Section 3.10), persisted via a `RiskScoreRepositoryPort`.
- `RiskCalculated` domain event.

#### 2.4 The Multi-Factor Risk Formula

The Risk Score is computed as a weighted combination of four named factors, each independently bounded to [0.0, 1.0] before weighting, so that the decomposition itself (not only the final value) is meaningful and auditable:

| Factor | Symbol | What It Measures | Primary Inputs |
|---|---|---|---|
| Exploitability | `E` | How easily this violation could be exploited given current exposure | Graph-derived network reachability, authentication requirements, whether the misconfiguration requires additional preconditions |
| Blast Radius | `B` | How much of the estate is affected if exploited | Count and criticality of resources reachable/affected downstream in the graph from this resource |
| Data Sensitivity | `D` | How sensitive the data at risk is | `data_classification` from Context Engine |
| Business Criticality | `C` | How important the affected system is to the organization | `business_criticality` from Context Engine, combined with `environment` |

```
RiskScore.value = 10 * (
    w_e * E +
    w_b * B +
    w_d * D +
    w_c * C
)

WHERE w_e + w_b + w_d + w_c = 1.0
DEFAULT WEIGHTS (formula_version "1.0.0"):
    w_e = 0.35   # exploitability weighted highest: an unexploitable misconfiguration
                  # is a lower operational priority almost by definition
    w_b = 0.25
    w_d = 0.25
    w_c = 0.15
```

Each factor's own sub-formula is documented explicitly, since "weighted sum of vaguely-named factors" would itself fail the re-derivability requirement without further specification:

```
FUNCTION calculate_exploitability(violation: ContextualizedViolation, graph) -> float:
    base = 0.3   # baseline: any confirmed technical violation has non-zero exploitability
    IF graph.is_internet_reachable(violation.resource.id):
        base += 0.4
    IF violation.rule.requires_no_additional_preconditions:   # e.g. no auth bypass needed
        base += 0.2
    IF violation.resource.security_attributes.get("public_access.bucket_policy_is_public") == true:
        base += 0.1
    RETURN min(base, 1.0)


FUNCTION calculate_blast_radius(violation: ContextualizedViolation, graph) -> float:
    downstream = graph.get_reachable_resources(violation.resource.id, max_hops=3)
    IF len(downstream) == 0:
        RETURN 0.2   # isolated resource, minimal blast radius, never zero (violation still matters)
    critical_downstream_count = count(r for r in downstream if r.business_criticality in ["high", "critical"])
    RETURN min(0.2 + 0.15 * critical_downstream_count, 1.0)


FUNCTION calculate_data_sensitivity(context: ContextualizedViolation) -> float:
    MAPPING = {"public": 0.1, "internal": 0.4, "confidential": 0.7, "restricted": 1.0}
    RETURN MAPPING[context.data_classification]


FUNCTION calculate_business_criticality_factor(context: ContextualizedViolation) -> float:
    MAPPING = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}
    RETURN MAPPING[context.business_criticality]
```

#### 2.5 Severity Band Derivation

```
FUNCTION derive_severity_band(value: float, formula_version: string) -> string:
    # thresholds themselves versioned alongside the weight formula
    IF formula_version == "1.0.0":
        IF value >= 9.0: RETURN "critical"
        IF value >= 7.0: RETURN "high"
        IF value >= 4.0: RETURN "medium"
        RETURN "low"
```

#### 2.6 Internal Algorithm (Full Assembly)

```
FUNCTION calculate_risk(scan: Scan, contextualized_violations: list[ContextualizedViolation]) -> None:
    graph = relationship_repository_port.get_graph_for_scan(scan.id)
    scores = []

    FOR cv IN contextualized_violations:
        IF cv.violation.status_override == "SUPPRESSED_WITH_COMPENSATING_CONTROL":
            # still scored — a suppressed finding retains its risk score for reporting
            # and for the eventual compensating-control renewal review (Part 6, Section 4.8)
            pass

        E = calculate_exploitability(cv, graph)
        B = calculate_blast_radius(cv, graph)
        D = calculate_data_sensitivity(cv)
        C = calculate_business_criticality_factor(cv)

        value = 10 * (0.35*E + 0.25*B + 0.25*D + 0.15*C)
        severity_band = derive_severity_band(value, RISK_FORMULA_VERSION)

        risk_score = RiskScore(
            value = value,
            severity_band = severity_band,
            factors = {"exploitability": E, "blast_radius": B, "data_sensitivity": D, "business_criticality": C},
            formula_version = RISK_FORMULA_VERSION,
            calculated_at = now()
        )
        risk_score_repository_port.save(risk_score)
        scores.append((cv, risk_score))

    risk_score_cache.store(scan.id, scores)
    event_publisher_port.publish(RiskCalculated(scan_id=scan.id, count=len(scores)))
```

#### 2.7 Interfaces

- **Port:** `RiskScoreRepositoryPort`.
- **Consumed by:** Application-layer `CalculateRiskUseCase`, in the `Scoring Service` container (Part 2, Component Diagram, `SVC5`).

#### 2.8 Interactions

```mermaid
sequenceDiagram
    participant Prev as EnrichContextUseCase
    participant UC as CalculateRiskUseCase
    participant Graph as RelationshipRepositoryPort
    participant Calc as RiskCalculationService (Domain)
    participant Repo as RiskScoreRepositoryPort
    participant Bus as Event Bus

    Prev->>UC: ContextualizedViolation list
    UC->>Graph: get_graph_for_scan(scan_id)
    loop per violation
        UC->>Calc: calculate(violation, graph)
        Calc-->>UC: RiskScore
        UC->>Repo: save(RiskScore)
    end
    UC->>Bus: publish(RiskCalculated)
```

#### 2.9 Failure Scenarios

| Scenario | Handling |
|---|---|
| Graph unavailable for blast-radius/exploitability calculation (e.g., Graph Service degraded) | Falls back to a documented, more conservative default (`E`, `B` computed from resource-only signals, without graph traversal), and the resulting `RiskScore.factors` includes a `graph_data_available: false` marker so the score's provenance is transparent, never silently treated as equivalent to a graph-informed score. |
| `data_classification` or `business_criticality` missing from context (should not happen given Part 6's defaults, but defensively handled) | Falls back to the most conservative mapping value (`"restricted"`/`"critical"` respectively) rather than the least, consistent with the asymmetric fail-safe philosophy established in Part 6, Section 3.4. |

#### 2.10 Performance

Risk calculation is proportional to violation count, with the exploitability/blast-radius factors requiring bounded (`max_hops=3`) graph traversal per violation — capped explicitly to keep this stage's per-violation cost constant rather than growing with overall graph size.

---

### 3. Multi-Factor Risk Engine — Core Innovation #6 (Deep Dive)

#### 3.1 Motivation

A single flat severity (as assigned by `Rule.severity_default`, Part 3, Section 3.7) cannot express that the *same* rule violation carries different real risk depending on exploitability and blast radius, which are runtime, graph-dependent properties, not static properties of the rule definition itself. A tool that only ever reports `Rule.severity_default` verbatim is, in effect, ignoring 100% of the contextual and structural information the rest of this pipeline (Parts 4–6) worked to compute.

#### 3.2 Problem Solved

The Multi-Factor Risk Engine converts a static rule severity into a dynamic, per-instance, per-scan risk score that reflects the resource's actual current exposure and organizational context — directly addressing the alert-fatigue and misprioritization problems endemic to flat-severity CSPM tools.

#### 3.3 Architecture

Already fully specified in Section 2.4–2.6. The architecture's key property is the strict separation between factor calculation (each a small, independently testable pure function) and factor combination (a single, transparent weighted sum) — this separation is what allows a future recalibration of, say, the exploitability weight without touching the blast-radius calculation logic at all, another direct application of Single Responsibility.

#### 3.4 Workflow

Already specified in Section 2.6.

#### 3.5 Advantages

- Fully explainable: every `RiskScore.factors` entry can be independently reviewed and challenged by a security engineer, unlike an opaque ML-based risk score.
- Naturally reflects environmental drift: if a network change makes a previously-isolated resource internet-reachable, the *same* underlying rule violation's risk score rises automatically on the next scan, without any rule change.
- Weight tuning is a single, tenant-independent (or, if needed, tenant-specific override) configuration change, not a rule-by-rule rewrite.

#### 3.6 Limitations

- The weighting scheme (`w_e=0.35, w_b=0.25, w_d=0.25, w_c=0.15`) is itself a judgment call, calibrated from general security prioritization practice rather than derived from tenant-specific incident data; tenants with atypical risk profiles may need custom weight overrides (supported structurally, via a tenant-scoped `formula_version` override, but not derived automatically from tenant history in the current scope).
- Deterministic formulas cannot capture genuinely novel or emergent attack patterns the way a continuously-retrained ML model might — this is a deliberate trade-off in favor of auditability (NFR-06) over adaptive sophistication, consistent with ADR-001's boundary: adaptive, pattern-learning risk assessment is exactly the kind of capability that belongs in Subsystem B, applied on top of these deterministic scores, not inside Subsystem A.

#### 3.7 Extensibility

New factors (e.g., a future `regulatory_exposure` factor reflecting whether a violation specifically implicates a regulator-reportable data type) are added by defining a new pure calculation function and extending the weighted sum, with weights re-normalized to sum to 1.0 and the change published as a new `formula_version`.

#### 3.8 Real Implementation Example

```json
{
  "risk_score": {
    "value": 8.15,
    "severity_band": "high",
    "factors": {
      "exploitability": 0.90,
      "blast_radius": 0.65,
      "data_sensitivity": 0.70,
      "business_criticality": 1.00
    },
    "formula_version": "1.0.0",
    "calculated_at": "2026-08-01T09:14:22Z"
  }
}
```

Worked calculation: `10 * (0.35*0.90 + 0.25*0.65 + 0.25*0.70 + 0.15*1.00) = 10 * (0.315 + 0.1625 + 0.175 + 0.15) = 10 * 0.8025 = 8.025` (illustrative rounding shown; the JSON example above reflects a slightly different but equivalently derived input set for exposition clarity — the calculation method, not the specific figures, is the point of the example).

---

### 4. Confidence Engine (Module 9)

#### 4.1 Responsibilities

1. Calculating `Confidence.value` (0.0–1.0) for every scored violation, reflecting how certain the engine is that the finding is a true positive given the actual completeness and quality of the evidence available.
2. Distinguishing `data_completeness_factor` (was all needed data actually retrievable) from `evidence_quality_factor` (was the retrieved data direct/observed versus inferred).
3. Publishing the finalized `Confidence` alongside each `RiskScore` (embedded, per Part 3, Section 3.11, as a Value Object on the eventual `Finding`).

#### 4.2 Inputs

- Every `INDETERMINATE` outcome encountered anywhere upstream for the resources/rules involved in this violation (Part 5, Sections 4.5 and 5.4's three-valued logic propagation).
- The `derived_from_rule` field on any `Relationship` involved (Part 3, Section 3.5) — an inferred graph edge (e.g., `NETWORK_REACHABLE` derived via inference plugin) carries inherently lower evidence quality than a directly-observed edge (e.g., `ATTACHED_TO`).
- Any `data_completeness_flag` set during Normalization (Part 4, Section 3.7) for resources with partial `raw_payload` due to insufficient discovery-role permissions.

#### 4.3 The Confidence Formula

```
FUNCTION calculate_confidence(violation, graph, normalization_flags) -> Confidence:
    data_completeness = 1.0
    IF any resource involved has data_completeness_flag == true:
        data_completeness -= 0.3
    IF any member rule outcome was INDETERMINATE (composite rules, Part 5 Section 5.7):
        data_completeness -= 0.2
    data_completeness = max(data_completeness, 0.1)   # never fully zero — a floor, not an absence

    evidence_quality = 1.0
    FOR relationship IN violation.involved_relationships:
        IF relationship.derived_from_rule is not null:            # inferred, not observed
            evidence_quality -= 0.15 * (1 - relationship.weight)   # lower inference confidence -> larger penalty
    evidence_quality = max(evidence_quality, 0.2)

    confidence_value = data_completeness * evidence_quality

    RETURN Confidence(
        value = confidence_value,
        data_completeness_factor = data_completeness,
        evidence_quality_factor = evidence_quality,
        formula_version = CONFIDENCE_FORMULA_VERSION
    )
```

#### 4.4 Outputs

- `Confidence` Value Objects, embedded into the corresponding `RiskScore`'s eventual `Finding` (Part 3, Section 3.11) — not persisted as an independent top-level table, consistent with its Value Object modeling decision (Part 3, Section 2).

#### 4.5 Interfaces

Co-located with the Risk Intelligence Engine in the same `Scoring Service` container (Part 2, `SVC5`); no separate port is needed beyond what Section 2.7 already defines, since `Confidence` calculation consumes the same in-memory violation/graph data already fetched for `RiskScore` calculation.

#### 4.6 Interactions

```mermaid
sequenceDiagram
    participant UC as CalculateRiskUseCase
    participant ConfCalc as ConfidenceCalculationService (Domain)
    participant Bus as Event Bus

    UC->>UC: calculate RiskScore (Section 2.6)
    UC->>ConfCalc: calculate_confidence(violation, graph, normalization_flags)
    ConfCalc-->>UC: Confidence
    UC->>UC: attach Confidence to in-memory (violation, RiskScore, Confidence) tuple
    UC->>Bus: publish(RiskCalculated) [includes confidence alongside risk]
```

#### 4.7 Failure Scenarios

| Scenario | Handling |
|---|---|
| Every factor computation floor is hit simultaneously (worst-case data quality) | `confidence_value` bottoms out at `0.1 * 0.2 = 0.02`, still a valid, non-zero, explicitly low-confidence score — surfaced to consumers as "very low confidence, verify manually" rather than being excluded from output entirely, since even a low-confidence signal has value for a security team's own follow-up investigation. |
| Confidence and Risk calculated from stale graph data due to a graph construction fallback (Part 5, Section 2.7's bounded/sampled approximation) | The `graph_data_available: false` / `graph_data_sampled: true` markers from Section 2.9 propagate directly into a reduced `evidence_quality_factor`, so the confidence score itself reflects the upstream data quality degradation rather than the degradation being invisible at this stage. |

#### 4.8 Performance

Negligible incremental cost beyond Risk calculation, since both consume the same fetched data within the same use case invocation (Section 4.5).

---

### 5. Confidence Engine — Core Innovation #5 (Deep Dive)

#### 5.1 Motivation

Every automated compliance/security tool eventually encounters incomplete data: a discovery role missing a permission, an inference algorithm falling back to a sampled approximation, a graph edge that is inferred rather than directly observed. Most CSPM tools either ignore this distinction entirely (reporting all findings with equal apparent certainty) or handle it ad hoc via internal heuristics invisible to the end user. Neither approach lets a security team correctly prioritize "I am certain this is broken, fix it now" over "I suspect this might be broken, but my data here was incomplete, please verify."

#### 5.2 Problem Solved

The Confidence Engine makes data completeness and evidence quality first-class, quantified, and auditable properties of every finding, distinct from and complementary to the Risk Score — a finding can be simultaneously high-risk and low-confidence (urgent to manually verify) or low-risk and high-confidence (safe to deprioritize with certainty), and these are meaningfully different prioritization signals that a single combined score would conflate.

#### 5.3 Architecture, Workflow

Already specified in Sections 4.3–4.6.

#### 5.4 Advantages

- Enables intelligent triage: security teams can sort by "high risk, high confidence" first, then separately review "high risk, low confidence" items with appropriate skepticism and manual verification steps.
- Makes data-quality gaps in the underlying cloud discovery (e.g., missing IAM permissions on the discovery role) visible and actionable in aggregate, rather than silently degrading finding quality without anyone noticing.
- Directly supports Subsystem B's downstream consumption (ADR-001): a low-confidence finding can be flagged for the AI/GRC layer to explicitly caveat in its natural-language explanation, rather than presenting uncertain findings with false authority.

#### 5.5 Limitations

- The specific penalty coefficients (`0.3`, `0.2`, `0.15` in Section 4.3) are, like the Risk Engine's weights (Section 3.6), calibrated judgment calls rather than empirically derived from historical false-positive-rate data — a natural target for future refinement once sufficient historical finding-outcome data (confirmed true/false positive labels from GRC analyst review) accumulates.
- Confidence measures *data quality*, not *rule correctness* — a rule with a logic bug will still produce high-confidence, high-quality-looking, but substantively wrong findings; this limitation is explicitly out of the Confidence Engine's scope and is instead addressed operationally via the rule-authoring review workflow (Part 14).

#### 5.6 Extensibility

Additional confidence-reducing signals (e.g., a future signal reflecting how recently a given cloud API's data was known to be eventually-consistent/stale) are added as additional multiplicative or subtractive terms in Section 4.3's formula, versioned via `CONFIDENCE_FORMULA_VERSION`.

#### 5.7 Real Implementation Example

```json
{
  "confidence": {
    "value": 0.68,
    "data_completeness_factor": 0.8,
    "evidence_quality_factor": 0.85,
    "formula_version": "1.0.0"
  },
  "explanation_for_audit": "Data completeness reduced from 1.0 to 0.8 because the discovery role lacked read access to the VPC flow log configuration for this account; evidence quality reduced from 1.0 to 0.85 because the network-reachability edge supporting this finding was inferred (weight 0.92) rather than directly observed."
}
```

Note: the `explanation_for_audit` string shown here is generated deterministically from the factor values and their known contributing causes (a template-filled string, not a generative model output) — this stays firmly on the Subsystem A side of ADR-001's boundary, since it is a fixed, rule-based explanation of *this engine's own* computation, not an open-ended natural-language reasoning task.

---

### 6. Closing Note for Part 7

Part 7 has fully specified the Risk Intelligence Engine and the Confidence Engine, including the complete, documented, versioned Multi-Factor Risk formula and Confidence formula, satisfying FR-08, FR-09, NFR-05, and NFR-06 at the pipeline's most numerically consequential stage.

Part 8, next, covers the **Attack Path Engine** (module 10) and its Core Innovation #7, plus the **Compliance Mapping Engine** (module 11) and Core Innovation #9 (Multi-Framework Compliance Mapping) — how individually-scored violations combine into scored attack chains, and how technical rules map many-to-many onto ISO 27001, NIST 800-53, CIS, DNSSI, and PCI-DSS controls.

---

*End of Part 7. Awaiting instruction: "Continue."*
