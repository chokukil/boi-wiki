---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-009 Open-system balance",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:009",
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
      "ref": "sci-evidence:common:system-balance"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:009",
    "standard_id": "R-COM-009",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:open-system-inventory",
      "sci:concept:boundary-flow"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:open-system-inventory",
    "object_concept_id": "sci:concept:boundary-flow",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "system_boundary_defined",
        "operator": "eq",
        "value": true
      },
      {
        "key": "balance_quantity",
        "operator": "eq",
        "value": "total_mass"
      }
    ],
    "validity_conditions": [
      {
        "key": "flow_terms_accounted",
        "operator": "eq",
        "value": true
      }
    ],
    "knowledge_refs": [
      "sci:common:009"
    ],
    "evidence_refs": [
      "sci-evidence:common:system-balance"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:system-balance",
        "claim_family": "locator_bound.common.system_balance",
        "purpose": "This law asserts that the mass δM = ρδV of a material particle remains invariant."
      }
    ],
    "deterministic_evaluator": true,
    "expected_predicate": "can_change_with_flow",
    "contradiction_predicates": [
      "must_remain_constant"
    ],
    "expected_polarity": "positive",
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-COM-009 — Open-system balance

Closed evaluator: `directional_relation`. Candidate qualification only.
