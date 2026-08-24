---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-012 Correlation does not establish causation",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:012",
  "visibility": "public",
  "classification": "internal",
  "owner": "science-admin",
  "author": {
    "type": "agent",
    "agent_id": "codex"
  },
  "acl_policy": "acl:public",
  "status": "draft",
  "source_refs": [
    {
      "type": "boi",
      "ref": "sci-evidence:common:correlation-causation"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:012",
    "standard_id": "R-COM-012",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:correlation",
      "sci:concept:causation"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:correlation",
    "object_concept_id": "sci:concept:causation",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "observed_relation_basis",
        "operator": "eq",
        "value": "correlation_only"
      }
    ],
    "validity_conditions": [
      {
        "key": "causal_evidence_basis",
        "operator": "in",
        "values": [
          "correlation_only",
          "intervention_or_mechanism"
        ]
      }
    ],
    "knowledge_refs": [
      "sci:common:012"
    ],
    "evidence_refs": [
      "sci-evidence:common:correlation-causation"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:correlation-causation",
        "claim_family": "locator_bound.common.correlation_causation",
        "purpose": "Note that correlation does not imply causality. It is possible for two variables to be associated with each other without one of them causing the observed behavior in the other."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_012_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "correlation_coefficient": "dimensionless"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "correlation_coefficient",
        "quantity_kind": "correlation_coefficient",
        "reference_quantity_kind": "correlation_coefficient_reference"
      }
    ],
    "expected_predicate": "does_not_imply",
    "contradiction_predicates": [
      "implies",
      "proves"
    ],
    "expected_polarity": "positive"
  }
}
---
# R-COM-012 — Correlation does not establish causation

Closed evaluator: `directional_relation`. Candidate qualification only.
