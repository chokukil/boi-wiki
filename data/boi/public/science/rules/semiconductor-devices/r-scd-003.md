---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-003 Doping, mobility, and conductivity",
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
      "sci:concept:doping-change",
      "sci:concept:conductivity"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:doping-change",
    "object_concept_id": "sci:concept:conductivity",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "transport_regime",
        "operator": "eq",
        "value": "low_field"
      },
      {
        "key": "carrier_state_parameters_known",
        "operator": "eq",
        "value": true
      },
      {
        "key": "doping_change",
        "operator": "eq",
        "value": "specified_before_after_state"
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
        "key": "claim_specificity",
        "operator": "eq",
        "value": "equipment_or_numeric"
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
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-SCD-003 — Doping, mobility, and conductivity

Closed evaluator: `validity_domain`. Candidate qualification only.
