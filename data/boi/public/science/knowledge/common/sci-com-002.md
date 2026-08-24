---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "002 Dimensional homogeneity is necessary, not sufficient",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:002",
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
      "ref": "sci-evidence:common:quantity-unit-dimension"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:002",
    "foundation_topic_id": "SCI-COM-002",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "invariant",
    "assurance_basis": "hypothesis",
    "statement": "This executable example checks dimensional homogeneity only for equality between two length terms.",
    "definitions": [
      "quantity equation: a relation among quantities",
      "dimensional homogeneity: compatible dimensions across an equation",
      "sufficiency limit: dimension matching does not validate mechanisms or coefficients"
    ],
    "assumptions": [
      "Each equation term has a resolved quantity kind and unit."
    ],
    "applicability": {
      "scope": "quantity equations represented by registered units"
    },
    "limitations": [
      "A dimensionally homogeneous equation can still be false or outside its model domain."
    ],
    "invalid_outside": [
      "equations with unresolved terms",
      "claims treating dimensional consistency as proof"
    ],
    "related_knowledge": [
      "sci:common:001",
      "sci:common:008"
    ],
    "evidence_refs": [
      "sci-evidence:common:quantity-unit-dimension"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:quantity-unit-dimension",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-002 — Narrow reviewed Foundation statement

This executable example checks dimensional homogeneity only for equality between two length terms.

Candidate-only draft; authorized Admin review is absent.
