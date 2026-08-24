---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-PHY-005 Control-volume balance scope",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:physics:005",
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
      "ref": "sci-evidence:physics:control-volume-flux"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:physics:005",
    "standard_id": "R-PHY-005",
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:control-volume-balance",
      "sci:concept:moving-unsteady-flow"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:control-volume-balance",
    "object_concept_id": "sci:concept:moving-unsteady-flow",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "control_surface",
        "operator": "eq",
        "value": "explicit_closed_surface"
      }
    ],
    "validity_conditions": [
      {
        "key": "flux_accounting",
        "operator": "eq",
        "value": "boundary_and_accumulation_terms"
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
      "sci:physics:005"
    ],
    "evidence_refs": [
      "sci-evidence:physics:control-volume-flux"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:physics:control-volume-flux",
        "claim_family": "locator_bound.physics.control_volume_flux",
        "purpose": "Both forms A and B are valid for arbitrarily moving and deforming control volumes (i.e. control volumes that may be expanding, translating, accelerating, or whatever), and for unsteady as well as steady flows."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-PHY-005 — Control-volume balance scope

Closed evaluator: `validity_domain`. Candidate qualification only.
