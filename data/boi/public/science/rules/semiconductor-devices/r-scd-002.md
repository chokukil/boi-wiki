---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-002 Drift and diffusion current components",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:semiconductor-devices:002",
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
      "ref": "sci-evidence:semiconductor-devices:drift-diffusion"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:semiconductor-devices:002",
    "standard_id": "R-SCD-002",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:carrier-current",
      "sci:concept:drift-diffusion-components"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:carrier-current",
    "object_concept_id": "sci:concept:drift-diffusion-components",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "carrier_type",
        "operator": "eq",
        "value": "electron_or_hole"
      }
    ],
    "validity_conditions": [
      {
        "key": "transport_decomposition",
        "operator": "eq",
        "value": "drift_and_diffusion"
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
      "current_scale": "ampere"
    },
    "knowledge_refs": [
      "sci:semiconductor-devices:002"
    ],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:drift-diffusion"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:drift-diffusion",
        "claim_family": "locator_bound.semiconductor_devices.drift_diffusion",
        "purpose": "In addition to the drift current, there is a second component of current called the diffusion current."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-SCD-002 — Drift and diffusion current components

Closed evaluator: `validity_domain`. Candidate qualification only.
