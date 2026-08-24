---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-005 Ideal MOS gate-current model",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:semiconductor-devices:005",
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
      "ref": "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:semiconductor-devices:005",
    "standard_id": "R-SCD-005",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:ideal-mos-gate",
      "sci:concept:gate-current"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:ideal-mos-gate",
    "object_concept_id": "sci:concept:gate-current",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "model_regime",
        "operator": "eq",
        "value": "ideal_mos"
      },
      {
        "key": "gate_oxide_model",
        "operator": "eq",
        "value": "perfect_insulator"
      }
    ],
    "validity_conditions": [
      {
        "key": "claim_target",
        "operator": "eq",
        "value": "ideal_device"
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
      "film_thickness_scale": "nanometer"
    },
    "knowledge_refs": [
      "sci:semiconductor-devices:005"
    ],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:mos-gate-ideal-model",
        "claim_family": "semiconductor.mos_gate.ideal_zero_gate_current_model",
        "purpose": "The cited ideal model sets iG = 0 because the gate oxide is treated as insulating."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "zero",
    "contradiction_predicates": [
      "nonzero"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-SCD-005 — Ideal MOS gate-current model

Closed evaluator: `directional_relation`. Candidate qualification only.
