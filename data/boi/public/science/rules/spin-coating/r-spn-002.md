---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SPN-002 Model validation-domain record requirement",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:spin-coating:002",
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
    "rule_id": "sci-rule:spin-coating:002",
    "standard_id": "R-SPN-002",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:model-validation-domain-record",
      "sci:concept:record-maintenance"
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
    "empirical_trigger_conditions": [
      {
        "key": "requested_model_validation_record_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "validation_domain_temperature_limit": "kelvin"
    },
    "knowledge_refs": [
      "sci:spin-coating:002"
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

# R-SPN-002 — Model validation-domain record requirement

Closed evaluator: `validity_domain`. Candidate qualification only.
