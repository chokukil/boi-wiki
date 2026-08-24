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
    "subject_concept_id": "sci:concept:conditional-directional-claim",
    "object_concept_id": "sci:concept:controlled-relation",
    "relation_kind": "monotonic_direction",
    "required_conditions": [
      {
        "key": "input_quantity_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "response_quantity_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "relation_form_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "held_constant_variables_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "process_stage_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "material_state_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "temporal_basis_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "evidence_basis_identified",
        "operator": "eq",
        "value": true
      }
    ],
    "validity_conditions": [
      {
        "key": "valid_range_identified",
        "operator": "eq",
        "value": true
      },
      {
        "key": "regime_transition_checked",
        "operator": "eq",
        "value": true
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
        "purpose": "A record of the domain of validation of the M&S shall be maintained."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-COM-011 — Controlled directional claim

Closed evaluator: `validity_domain`. Candidate qualification only.
