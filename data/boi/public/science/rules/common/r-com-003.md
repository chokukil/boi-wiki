---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-003 Registered unit conversion kind",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:003",
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
      "ref": "sci-evidence:common:celsius-kelvin"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:003",
    "standard_id": "R-COM-003",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:celsius-temperature",
      "sci:concept:kelvin-temperature"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:celsius-temperature-interval",
    "object_concept_id": "sci:concept:kelvin-temperature-interval",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "comparison_kind",
        "operator": "eq",
        "value": "unit_interval_magnitude"
      }
    ],
    "validity_conditions": [
      {
        "key": "unit_pair",
        "operator": "eq",
        "value": "degree_celsius_kelvin"
      }
    ],
    "knowledge_refs": [
      "sci:common:003"
    ],
    "evidence_refs": [
      "sci-evidence:common:celsius-kelvin"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:celsius-kelvin",
        "claim_family": "locator_bound.common.celsius_kelvin",
        "purpose": "The unit of Celsius temperature is the degree Celsius, symbol °C, which is by definition equal in magnitude to the unit kelvin."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_003_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "temperature_interval": "kelvin"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "temperature_interval",
        "quantity_kind": "temperature_interval",
        "reference_quantity_kind": "temperature_interval_reference",
        "interval": true
      }
    ]
  }
}
---
# R-COM-003 — Registered unit conversion kind

Closed evaluator: `equation_constraint`. Candidate qualification only.
