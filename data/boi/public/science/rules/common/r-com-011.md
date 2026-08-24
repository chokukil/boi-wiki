---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-011 Controlled directional claim",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:011",
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
      "ref": "sci-evidence:common:model-validity"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:011",
    "standard_id": "R-COM-011",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:conditional-directional-claim",
      "sci:concept:controlled-relation"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:model-validation-domain-record",
    "object_concept_id": "sci:concept:validation-domain",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "record_identity",
        "operator": "eq",
        "value": "bound_validation_record"
      }
    ],
    "validity_conditions": [
      {
        "key": "record_content",
        "operator": "eq",
        "value": "validation_domain"
      }
    ],
    "knowledge_refs": [
      "sci:common:011"
    ],
    "evidence_refs": [
      "sci-evidence:common:model-validity"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:model-validity",
        "claim_family": "locator_bound.common.model_validity",
        "purpose": "A record of the domain of validation of the validated M&S shall be maintained."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_011_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "validation_domain_temperature_limit": "kelvin"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "validation_domain_temperature_limit",
        "quantity_kind": "validation_domain_temperature_limit",
        "reference_quantity_kind": "validation_domain_temperature_limit_reference"
      }
    ]
  }
}
---
# R-COM-011 — Controlled directional claim

Closed evaluator: `validity_domain`. Candidate qualification only.
