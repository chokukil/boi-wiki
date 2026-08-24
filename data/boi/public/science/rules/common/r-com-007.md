---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-007 Repeatability and reproducibility conditions",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:007",
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
      "ref": "sci-evidence:common:repeatability-reproducibility"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:007",
    "standard_id": "R-COM-007",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:repeatability-condition",
      "sci:concept:reproducibility-condition"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:repeatability-condition",
    "object_concept_id": "sci:concept:reproducibility-condition",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "changed_conditions_identified",
        "operator": "eq",
        "value": true
      }
    ],
    "validity_conditions": [
      {
        "key": "comparison_scope",
        "operator": "eq",
        "value": "precision_conditions"
      }
    ],
    "knowledge_refs": [
      "sci:common:007"
    ],
    "evidence_refs": [
      "sci-evidence:common:repeatability-reproducibility"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:repeatability-reproducibility",
        "claim_family": "measurement.reproducibility_definition_only",
        "purpose": "The cited span may support only the VIM definition of a reproducibility condition, not a full repeatability-versus-reproducibility comparison."
      }
    ],
    "deterministic_evaluator": true,
    "expected_predicate": "distinct_from",
    "contradiction_predicates": [
      "interchangeable_with"
    ],
    "expected_polarity": "positive",
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-COM-007 — Repeatability and reproducibility conditions

Closed evaluator: `directional_relation`. Candidate qualification only.
