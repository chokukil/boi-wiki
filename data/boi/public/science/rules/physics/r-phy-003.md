---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-PHY-003 Work and kinetic-energy change",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:physics:003",
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
      "ref": "sci-evidence:physics:work-energy-power"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:physics:003",
    "standard_id": "R-PHY-003",
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "rule_kind": "equation_constraint",
    "inputs": [
      "sci:concept:applied-force-work",
      "sci:concept:kinetic-energy-change"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:applied-force-work",
    "object_concept_id": "sci:concept:kinetic-energy-change",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "object_system",
        "operator": "eq",
        "value": "explicit_bounded_object"
      }
    ],
    "validity_conditions": [
      {
        "key": "work_accounting",
        "operator": "eq",
        "value": "all_applied_work_terms"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_work_energy_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "energy_scale": "joule"
    },
    "knowledge_refs": [
      "sci:physics:003"
    ],
    "evidence_refs": [
      "sci-evidence:physics:work-energy-power"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:physics:work-energy-power",
        "claim_family": "locator_bound.physics.work_energy_power",
        "purpose": "the work done by the applied force on an object is identically equal to the change in kinetic energy of the object."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equation": {
      "left_quantity_kind": "applied_work",
      "right_quantity_kinds": [
        "kinetic_energy_change"
      ],
      "operator": "equal"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "energy_scale",
        "quantity_kind": "energy_scale",
        "reference_quantity_kind": "energy_scale_reference"
      }
    ]
  }
}
---

# R-PHY-003 — Work and kinetic-energy change

Closed evaluator: `equation_constraint`. Candidate qualification only.
