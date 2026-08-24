---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SPN-001 Spin-film measurement state",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:spin-coating:001",
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
      "ref": "sci-evidence:common:measurand-result"
    },
    {
      "type": "boi",
      "ref": "sci-evidence:spin-coating:microchemicals-film-state-change"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:spin-coating:001",
    "standard_id": "R-SPN-001",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:film-thickness-result",
      "sci:concept:measurement-state"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:film-thickness-result",
    "object_concept_id": "sci:concept:measurement-state",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "material_state",
        "operator": "eq",
        "value": "dry_post_bake_or_explicit_state"
      },
      {
        "key": "uncertainty_record",
        "operator": "eq",
        "value": "value_unit_and_coverage_bound"
      },
      {
        "key": "material_class",
        "operator": "eq",
        "value": "photoresist"
      },
      {
        "key": "process_method",
        "operator": "eq",
        "value": "spin_coating"
      }
    ],
    "validity_conditions": [
      {
        "key": "comparison_target",
        "operator": "eq",
        "value": "film_thickness_between_named_states"
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
      "sci:spin-coating:001"
    ],
    "evidence_refs": [
      "sci-evidence:common:measurand-result",
      "sci-evidence:spin-coating:microchemicals-film-state-change"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:measurand-result",
        "claim_family": "locator_bound.common.measurand_result",
        "purpose": "A measurement result is generally expressed as a single measured quantity value and a measurement uncertainty."
      },
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-film-state-change",
        "claim_family": "spin_coating.film_thickness.process_state_difference",
        "purpose": "A thickness measured immediately after spin coating can change further as residual solvent evaporates, so the measurement state must remain explicit when thicknesses are compared."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-SPN-001 — Spin-film measurement state

Closed evaluator: `validity_domain`. Candidate qualification only.
