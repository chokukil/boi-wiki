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
    "rule_kind": "equation_constraint",
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
    "subject_concept_id": "sci:concept:celsius-temperature",
    "object_concept_id": "sci:concept:kelvin-temperature",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "conversion_kind",
        "operator": "eq",
        "value": "affine"
      }
    ],
    "validity_conditions": [
      {
        "key": "conversion_definition_registered",
        "operator": "eq",
        "value": true
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
    "equation": {
      "left_quantity_kind": "converted_temperature",
      "right_quantity_kinds": [
        "reference_temperature"
      ],
      "operator": "equal",
      "relative_tolerance": "0"
    },
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-COM-003 — Registered unit conversion kind

Closed evaluator: `equation_constraint`. Candidate qualification only.
