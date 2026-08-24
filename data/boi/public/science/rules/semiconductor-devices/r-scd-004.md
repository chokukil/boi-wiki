---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-004 Forward bias lowers a pn-junction barrier",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:semiconductor-devices:004",
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
      "ref": "sci-evidence:semiconductor-devices:pn-junction"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:semiconductor-devices:004",
    "standard_id": "R-SCD-004",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:forward-bias",
      "sci:concept:pn-junction-barrier"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:forward-bias",
    "object_concept_id": "sci:concept:pn-junction-barrier",
    "relation_kind": "monotonic_direction",
    "required_conditions": [
      {
        "key": "junction_type",
        "operator": "eq",
        "value": "pn"
      },
      {
        "key": "bias_polarity",
        "operator": "eq",
        "value": "forward"
      }
    ],
    "validity_conditions": [
      {
        "key": "device_model",
        "operator": "eq",
        "value": "pn_junction_barrier"
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
      "voltage_scale": "volt"
    },
    "knowledge_refs": [
      "sci:semiconductor-devices:004"
    ],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:pn-junction"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:pn-junction",
        "claim_family": "locator_bound.semiconductor_devices.pn_junction",
        "purpose": "a forward bias of V reduces the barrier height from φbi to φbi – V. This reduces the drift field and upsets the balance between diffusion and drift that exists at zero bias."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "decreases",
    "contradiction_predicates": [
      "increases"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-SCD-004 — Forward bias lowers a pn-junction barrier

Closed evaluator: `directional_relation`. Candidate qualification only.
