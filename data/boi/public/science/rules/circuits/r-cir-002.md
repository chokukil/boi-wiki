---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CIR-002 Kirchhoff voltage law",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:circuits:002",
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
      "ref": "sci-evidence:circuits:kvl-law"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:circuits:002",
    "standard_id": "R-CIR-002",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "rule_kind": "equation_constraint",
    "inputs": [
      "sci:concept:loop-voltage-sum",
      "sci:concept:zero-voltage"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:loop-voltage-sum",
    "object_concept_id": "sci:concept:zero-voltage",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "voltage_reference_convention",
        "operator": "eq",
        "value": "consistent"
      },
      {
        "key": "loop_path",
        "operator": "eq",
        "value": "bound_closed_path"
      }
    ],
    "validity_conditions": [
      {
        "key": "circuit_context",
        "operator": "eq",
        "value": "lumped_loop"
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
      "sci:circuits:002"
    ],
    "evidence_refs": [
      "sci-evidence:circuits:kvl-law"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:circuits:kvl-law",
        "claim_family": "circuits.kvl.loop_voltage_sum_zero",
        "purpose": "The algebraic sum of voltages around a loop is zero under consistent polarity and traversal conventions."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equation": {
      "left_quantity_kind": "algebraic_voltage_sum",
      "right_quantity_kinds": [
        "zero_voltage"
      ],
      "operator": "equal"
    }
  }
}
---

# R-CIR-002 — Kirchhoff voltage law

Closed evaluator: `equation_constraint`. Candidate qualification only.
