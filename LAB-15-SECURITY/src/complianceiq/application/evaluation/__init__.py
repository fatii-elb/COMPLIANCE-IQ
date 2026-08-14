"""AI evaluation harnesses — measuring answer quality, not just retrieval.

Phase 3 measured *retrieval* (recall@k, precision@k, MRR). This package measures
the **grounding** of the generated answers: does a capability actually attach
verified citations when sources exist, abstain when they don't, and cite the
*right* controls? Grounding is the product's core guarantee, so it must be
measurable, not merely asserted.
"""

from complianceiq.application.evaluation.grounding_eval import (
    GroundingEvalCase,
    GroundingEvaluator,
    GroundingMetrics,
)

__all__ = ["GroundingEvalCase", "GroundingEvaluator", "GroundingMetrics"]
