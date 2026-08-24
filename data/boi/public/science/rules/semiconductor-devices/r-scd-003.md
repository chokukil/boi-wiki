---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-003 Carrier-state conductivity relation",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:semiconductor-devices:003",
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
      "ref": "sci-evidence:semiconductor-devices:carrier-conductivity"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:semiconductor-devices:003",
    "standard_id": "R-SCD-003",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:carrier-state-parameters",
      "sci:concept:conductivity"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:carrier-state-parameters",
    "object_concept_id": "sci:concept:conductivity",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "transport_regime",
        "operator": "eq",
        "value": "low_field"
      },
      {
        "key": "carrier_parameter_scope",
        "operator": "eq",
        "value": "electron_and_hole_concentrations_and_mobilities"
      }
    ],
    "validity_conditions": [
      {
        "key": "relation_context",
        "operator": "eq",
        "value": "carrier_conductivity"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_carrier_conductivity_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "conductivity_scale": "siemens / meter"
    },
    "knowledge_refs": [
      "sci:semiconductor-devices:003"
    ],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:carrier-conductivity"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:carrier-conductivity",
        "claim_family": "semiconductor.low_field_carrier_conductivity",
        "purpose": "The cited low-field relation expresses conductivity as σ = qnµn + qpµp."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "carrier_conductivity_constraint": {
      "electron_concentration_kind": "electron_concentration",
      "hole_concentration_kind": "hole_concentration",
      "electron_mobility_kind": "electron_mobility",
      "hole_mobility_kind": "hole_mobility",
      "conductivity_kind": "conductivity",
      "relative_tolerance": "1e-12"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "conductivity_scale",
        "quantity_kind": "conductivity_scale",
        "reference_quantity_kind": "conductivity_scale_reference"
      }
    ]
  }
}
---

# R-SCD-003 — Carrier-state conductivity relation

Closed evaluator: `validity_domain` with a typed carrier-conductivity cross-field check. Candidate qualification only.
