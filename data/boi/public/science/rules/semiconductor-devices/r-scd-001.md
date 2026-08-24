---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SCD-001 Fermi occupation probability",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:semiconductor-devices:001",
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
      "ref": "sci-evidence:semiconductor-devices:bands-fermi-level"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:semiconductor-devices:001",
    "standard_id": "R-SCD-001",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:fermi-function",
      "sci:concept:state-occupation-probability"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:fermi-function",
    "object_concept_id": "sci:concept:state-occupation-probability",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "energy_state",
        "operator": "eq",
        "value": "bound_available_state"
      }
    ],
    "validity_conditions": [
      {
        "key": "statistics_model",
        "operator": "eq",
        "value": "fermi_dirac"
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
      "carrier_energy": "electron_volt"
    },
    "knowledge_refs": [
      "sci:semiconductor-devices:001"
    ],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:bands-fermi-level"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:bands-fermi-level",
        "claim_family": "locator_bound.semiconductor_devices.bands_fermi_level",
        "purpose": "EF is called the Fermi energy or the Fermi level. f(E) is the probability of a state at energy E being occupied by an electron."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-SCD-001 — Fermi occupation probability

Closed evaluator: `validity_domain`. Candidate qualification only.
