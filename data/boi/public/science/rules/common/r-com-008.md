---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-008 Model assumptions and validity domain",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:008",
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
    "rule_id": "sci-rule:common:008",
    "standard_id": "R-COM-008",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:model",
      "sci:concept:intended-use"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:model-validation-domain-record",
    "object_concept_id": "sci:concept:record-maintenance",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "model_identity",
        "operator": "eq",
        "value": "named_model"
      },
      {
        "key": "validation_record_scope",
        "operator": "eq",
        "value": "same_model"
      }
    ],
    "validity_conditions": [
      {
        "key": "record_maintenance_context",
        "operator": "eq",
        "value": "model_validation"
      }
    ],
    "knowledge_refs": [
      "sci:common:008"
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
        "key": "requested_foundation_008_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "validation_domain_length_limit": "meter"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "validation_domain_length_limit",
        "quantity_kind": "validation_domain_length_limit",
        "reference_quantity_kind": "validation_domain_length_limit_reference"
      }
    ]
  }
}
---
# R-COM-008 — Model assumptions and validity domain

Closed evaluator: `empirical_boundary`. Candidate qualification only.
