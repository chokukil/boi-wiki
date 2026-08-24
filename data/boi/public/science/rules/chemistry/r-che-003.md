---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CHE-003 Vapor pressure and escaping tendency",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:chemistry:003",
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
      "ref": "sci-evidence:chemistry:evaporation-vapor-pressure"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:chemistry:003",
    "standard_id": "R-CHE-003",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:vapor-pressure",
      "sci:concept:molecular-escaping-tendency"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:vapor-pressure",
    "object_concept_id": "sci:concept:molecular-escaping-tendency",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "condensed_substance",
        "operator": "eq",
        "value": "named_liquid_or_solid"
      }
    ],
    "validity_conditions": [
      {
        "key": "claim_scope",
        "operator": "eq",
        "value": "escaping_tendency_only"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "claim_specificity",
        "operator": "eq",
        "value": "equipment_or_numeric"
      }
    ],
    "context_dimensions": {
      "pressure_scale": "pascal"
    },
    "knowledge_refs": [
      "sci:chemistry:003"
    ],
    "evidence_refs": [
      "sci-evidence:chemistry:evaporation-vapor-pressure"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:chemistry:evaporation-vapor-pressure",
        "claim_family": "locator_bound.chemistry.evaporation_vapor_pressure",
        "purpose": "The vapor pressure is a direct measure of the escaping tendency of molecules from a condensed state of matter."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-CHE-003 — Vapor pressure and escaping tendency

Closed evaluator: `validity_domain`. Candidate qualification only.
