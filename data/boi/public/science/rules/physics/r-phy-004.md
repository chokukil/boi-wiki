---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-PHY-004 Simple fluid deforms under shear",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:physics:004",
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
      "ref": "sci-evidence:physics:viscosity-flow"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:physics:004",
    "standard_id": "R-PHY-004",
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:shear-stress",
      "sci:concept:simple-fluid-deformation"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:shear-stress",
    "object_concept_id": "sci:concept:simple-fluid-deformation",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "material_response_class",
        "operator": "eq",
        "value": "simple_fluid"
      },
      {
        "key": "shear_stress_state",
        "operator": "eq",
        "value": "nonzero_applied"
      }
    ],
    "validity_conditions": [
      {
        "key": "description_regime",
        "operator": "eq",
        "value": "continuum"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_fluid_deformation_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "dynamic_viscosity": "pascal * second"
    },
    "knowledge_refs": [
      "sci:physics:004"
    ],
    "evidence_refs": [
      "sci-evidence:physics:viscosity-flow"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:physics:viscosity-flow",
        "claim_family": "locator_bound.physics.viscosity_flow",
        "purpose": "The defining attribute of a simple fluid, however, is that it keeps deforming, or straining, as long as any shear stress, no matter how small, is applied to it."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "continues",
    "contradiction_predicates": [
      "stops"
    ],
    "expected_polarity": "positive",
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

# R-PHY-004 — Simple fluid deforms under shear

Closed evaluator: `directional_relation`. Candidate qualification only.
