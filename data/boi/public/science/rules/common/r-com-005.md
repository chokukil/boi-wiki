---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-005 Measurement uncertainty and error",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:005",
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
      "ref": "sci-evidence:common:uncertainty-error"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:005",
    "standard_id": "R-COM-005",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:measurement-uncertainty",
      "sci:concept:measurement-error"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:measurement-uncertainty",
    "object_concept_id": "sci:concept:dispersion-parameter",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "parameter_sign",
        "operator": "eq",
        "value": "non_negative"
      }
    ],
    "validity_conditions": [
      {
        "key": "definition_context",
        "operator": "eq",
        "value": "vim_measurement_uncertainty"
      }
    ],
    "knowledge_refs": [
      "sci:common:005"
    ],
    "evidence_refs": [
      "sci-evidence:common:uncertainty-error"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:uncertainty-error",
        "claim_family": "measurement.uncertainty_definition_only",
        "purpose": "The cited span may support only the VIM definition of measurement uncertainty, not a contrast with measurement error."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_005_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "uncertainty_parameter": "meter"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "uncertainty_parameter",
        "quantity_kind": "uncertainty_parameter",
        "reference_quantity_kind": "uncertainty_parameter_reference"
      }
    ]
  }
}
---
# R-COM-005 — Measurement uncertainty and error

Closed evaluator: `directional_relation`. Candidate qualification only.
