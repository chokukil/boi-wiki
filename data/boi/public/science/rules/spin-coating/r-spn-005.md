---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SPN-005 Equipment-specific thickness requires measurement",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:spin-coating:005",
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
    },
    {
      "type": "boi",
      "ref": "sci-evidence:spin-coating:microchemicals-equipment-influence"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:spin-coating:005",
    "standard_id": "R-SPN-005",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:equipment-specific-spin-result",
      "sci:concept:qualified-observation"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:equipment-specific-spin-result",
    "object_concept_id": "sci:concept:qualified-observation",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "validation_domain_ref",
        "operator": "eq",
        "value": "bound_science_knowledge"
      },
      {
        "key": "material_state",
        "operator": "eq",
        "value": "dry_post_bake_or_explicit_state"
      },
      {
        "key": "material_class",
        "operator": "eq",
        "value": "photoresist"
      },
      {
        "key": "process_method",
        "operator": "eq",
        "value": "spin_coating"
      },
      {
        "key": "thinning_continues_until",
        "operator": "eq",
        "value": "drying_stops_flow"
      }
    ],
    "validity_conditions": [
      {
        "key": "claim_scope",
        "operator": "eq",
        "value": "qualification_requirement_only"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_coater_transfer_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "film_thickness_scale": "nanometer"
    },
    "knowledge_refs": [
      "sci:spin-coating:005"
    ],
    "evidence_refs": [
      "sci-evidence:common:model-validity",
      "sci-evidence:spin-coating:microchemicals-equipment-influence"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:model-validity",
        "claim_family": "locator_bound.common.model_validity",
        "purpose": "A record of the domain of validation of the validated M&S shall be maintained."
      },
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-equipment-influence",
        "claim_family": "spin_coating.equipment.coating_result_influence",
        "purpose": "Spin-coating equipment can materially influence the coating result, so an exact equipment-specific result cannot be transferred from a general mechanism alone."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "film_thickness_scale",
        "quantity_kind": "film_thickness_scale",
        "reference_quantity_kind": "film_thickness_scale_reference"
      }
    ]
  }
}
---
# R-SPN-005 — Equipment-specific thickness requires measurement

Closed evaluator: `validity_domain`. Candidate qualification only.
