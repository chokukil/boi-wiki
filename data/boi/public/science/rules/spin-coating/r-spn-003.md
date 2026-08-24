---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SPN-003 Evaporation-aware spin-model limits",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:spin-coating:003",
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
      "ref": "sci-evidence:spin-coating:microchemicals-spin-mechanism"
    },
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
    "rule_id": "sci-rule:spin-coating:003",
    "standard_id": "R-SPN-003",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:evaporation-aware-spin-model",
      "sci:concept:dry-film-thickness"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
    "object_concept_id": "sci:concept:dry-film-thickness",
    "relation_kind": "equation",
    "required_conditions": [
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
        "key": "solvent_evaporation_model",
        "operator": "eq",
        "value": "explicit_term"
      },
      {
        "key": "validation_domain_ref",
        "operator": "eq",
        "value": "bound_science_knowledge"
      }
    ],
    "validity_conditions": [
      {
        "key": "thinning_termination",
        "operator": "eq",
        "value": "drying_relevant"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_evaporation_model_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "dynamic_viscosity": "pascal * second"
    },
    "knowledge_refs": [
      "sci:spin-coating:003"
    ],
    "evidence_refs": [
      "sci-evidence:spin-coating:microchemicals-spin-mechanism",
      "sci-evidence:common:model-validity"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-spin-mechanism",
        "claim_family": "spin_coating.mechanism.centrifugal_spreading_solvent_evaporation",
        "purpose": "Spin coating spreads photoresist and removes excess material while concurrent solvent evaporation contributes to stopping further thinning."
      },
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
        "scientific_role": "dynamic_viscosity",
        "quantity_kind": "dynamic_viscosity",
        "reference_quantity_kind": "dynamic_viscosity_reference"
      }
    ]
  }
}
---
# R-SPN-003 — Evaporation-aware spin-model limits

Closed evaluator: `validity_domain`. Candidate qualification only.
