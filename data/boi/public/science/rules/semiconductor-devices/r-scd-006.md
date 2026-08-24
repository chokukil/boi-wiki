---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-006 Real ultrathin SiO2 gate leakage",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:semiconductor-devices:006",
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
      "ref": "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:semiconductor-devices:006",
    "standard_id": "R-SCD-006",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:real-ultrathin-sio2-gate",
      "sci:concept:gate-leakage"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
    "object_concept_id": "sci:concept:gate-leakage",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "gate_dielectric",
        "operator": "eq",
        "value": "SiO2"
      },
      {
        "key": "oxide_thickness_nm",
        "operator": "lt",
        "value": 1.5,
        "unit": "nm"
      },
      {
        "key": "device_realization",
        "operator": "eq",
        "value": "physical_device"
      }
    ],
    "validity_conditions": [
      {
        "key": "leakage_mechanism",
        "operator": "eq",
        "value": "oxide_tunneling"
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
      "sci:semiconductor-devices:006"
    ],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:mos-gate-real-leakage",
        "claim_family": "semiconductor.mos_gate.ultrathin_sio2_tunneling_limit",
        "purpose": "The cited source identifies tunneling leakage as a limiting factor for SiO2 below its stated thickness."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "can_be_nonzero",
    "contradiction_predicates": [
      "always_zero"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-SCD-006 — Real ultrathin SiO2 gate leakage

Closed evaluator: `directional_relation`. Candidate qualification only.
