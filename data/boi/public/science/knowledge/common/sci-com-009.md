---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "009 Open-system balance",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:009",
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
    "knowledge_id": "sci:common:009",
    "foundation_topic_id": "SCI-COM-009",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "invariant",
    "assurance_basis": "hypothesis",
    "statement": "The cited material-particle mass remains invariant; this draft does not infer an open-control-volume inventory balance from that sentence.",
    "definitions": [
      "system boundary: surface separating system and surroundings",
      "inventory: amount stored inside the boundary",
      "flow term: transport across the boundary",
      "source or sink: allowed generation or consumption"
    ],
    "assumptions": [
      "Boundary, balance target, and sign convention are specified."
    ],
    "applicability": {
      "scope": "open-system balance claims"
    },
    "limitations": [
      "The Evidence states material-particle mass invariance; control-volume transformation remains an Admin-review-required draft."
    ],
    "invalid_outside": [
      "undefined boundaries",
      "balances mixing total mass and species mass"
    ],
    "related_knowledge": [
      "sci:common:001",
      "sci:common:010"
    ],
    "evidence_refs": [
      "sci-evidence:common:system-balance"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:system-balance",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-009 — Narrow reviewed Foundation statement

The cited material-particle mass remains invariant; this draft does not infer an open-control-volume inventory balance from that sentence.

Candidate-only draft; authorized Admin review is absent.
