---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-006 Accuracy, precision, and trueness",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:006",
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
      "ref": "sci-evidence:common:accuracy-precision"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:006",
    "standard_id": "R-COM-006",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:measurement-accuracy",
      "sci:concept:measurement-precision"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:measurement-accuracy",
    "object_concept_id": "sci:concept:measurement-precision",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "terminology_context",
        "operator": "eq",
        "value": "metrology"
      }
    ],
    "validity_conditions": [
      {
        "key": "manufacturer_term_definition",
        "operator": "eq",
        "value": "resolved"
      }
    ],
    "knowledge_refs": [
      "sci:common:006"
    ],
    "evidence_refs": [
      "sci-evidence:common:accuracy-precision"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:accuracy-precision",
        "claim_family": "locator_bound.common.accuracy_precision",
        "purpose": "The term “measurement accuracy” should not be used for measurement trueness and the term “measurement precision” should not be used for ‘measurement accuracy’, which, however, is related to both these concepts."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_006_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "accuracy_assessment_error": "meter"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "accuracy_assessment_error",
        "quantity_kind": "accuracy_assessment_error",
        "reference_quantity_kind": "accuracy_assessment_error_reference"
      }
    ],
    "expected_predicate": "distinct_from",
    "contradiction_predicates": [
      "interchangeable_with"
    ],
    "expected_polarity": "positive"
  }
}
---
# R-COM-006 — Accuracy, precision, and trueness

Closed evaluator: `directional_relation`. Candidate qualification only.
