---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CIR-001 Kirchhoff current law",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:circuits:001",
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
      "ref": "sci-evidence:circuits:kcl-law"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:circuits:001",
    "standard_id": "R-CIR-001",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "rule_kind": "equation_constraint",
    "inputs": [
      "sci:concept:node-current-sum",
      "sci:concept:zero-current"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:node-current-sum",
    "object_concept_id": "sci:concept:zero-current",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "current_reference_convention",
        "operator": "eq",
        "value": "consistent"
      },
      {
        "key": "circuit_model",
        "operator": "eq",
        "value": "lumped_matter"
      },
      {
        "key": "node_charge_accumulation",
        "operator": "eq",
        "value": "none"
      },
      {
        "key": "node_identity",
        "operator": "eq",
        "value": "bound_node_reference"
      }
    ],
    "validity_conditions": [
      {
        "key": "balance_context",
        "operator": "eq",
        "value": "kcl_node_sum"
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
      "sci:circuits:001"
    ],
    "evidence_refs": [
      "sci-evidence:circuits:kcl-law"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:circuits:kcl-law",
        "claim_family": "circuits.kcl.algebraic_current_sum_zero",
        "purpose": "The algebraic sum of currents at a node is zero under a consistent direction convention."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equation": {
      "left_quantity_kind": "algebraic_current_sum",
      "right_quantity_kinds": [
        "zero_current"
      ],
      "operator": "equal"
    }
  }
}
---

# R-CIR-001 — Kirchhoff current law

Closed evaluator: `equation_constraint`. Candidate qualification only.
