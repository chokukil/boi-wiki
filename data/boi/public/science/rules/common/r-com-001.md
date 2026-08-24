---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-001 Quantity, value, unit, and dimension",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:001",
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
      "ref": "sci-evidence:common:quantity-unit-dimension"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:001",
    "standard_id": "R-COM-001",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "dimension_constraint",
    "inputs": [
      "sci:concept:sample-length",
      "sci:concept:measurement-unit"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:sample-length",
    "object_concept_id": "sci:concept:measurement-unit",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "quantity_role",
        "operator": "eq",
        "value": "sample_length"
      }
    ],
    "validity_conditions": [
      {
        "key": "coverage_scope",
        "operator": "eq",
        "value": "sample_length_example"
      }
    ],
    "knowledge_refs": [
      "sci:common:001"
    ],
    "evidence_refs": [
      "sci-evidence:common:quantity-unit-dimension"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:quantity-unit-dimension",
        "claim_family": "locator_bound.common.quantity_unit_dimension",
        "purpose": "Physical quantities can be organized in a system of dimensions, where the system used is decided by convention. Each of the seven base quantities used in the SI is regarded as having its own dimension."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_001_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {},
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "sample_length",
        "quantity_kind": "sample_length",
        "reference_quantity_kind": "sample_length_reference"
      }
    ],
    "expected_dimensions": {
      "sample_length": "meter"
    }
  }
}
---
# R-COM-001 — Quantity, value, unit, and dimension

Closed evaluator: `dimension_constraint`. Candidate qualification only.
