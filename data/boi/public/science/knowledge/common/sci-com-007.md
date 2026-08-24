---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "007 Repeatability and reproducibility conditions",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:007",
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
      "ref": "sci-evidence:common:repeatability-reproducibility"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:007",
    "foundation_topic_id": "SCI-COM-007",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "Repeatability, intermediate precision, and reproducibility describe precision under different condition sets and must be labeled by the conditions that actually changed.",
    "definitions": [
      "repeatability condition: same procedure, operator, system, location, and short interval",
      "intermediate precision: selected changes within one laboratory",
      "reproducibility condition: different locations, operators, or systems"
    ],
    "assumptions": [
      "Changed and held conditions are identified."
    ],
    "applicability": {
      "scope": "precision statements about repeated measurements"
    },
    "limitations": [
      "The Evidence directly defines reproducibility conditions only."
    ],
    "invalid_outside": [
      "repeatability used as a generic reliability synonym",
      "undocumented condition sets"
    ],
    "related_knowledge": [
      "sci:common:004",
      "sci:common:006"
    ],
    "evidence_refs": [
      "sci-evidence:common:repeatability-reproducibility"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:repeatability-reproducibility",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-007 — Repeatability and reproducibility conditions

Repeatability, intermediate precision, and reproducibility describe precision under different condition sets and must be labeled by the conditions that actually changed.

This candidate draft requires authorized Admin review before active decision use.
