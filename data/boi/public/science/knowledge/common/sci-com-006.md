---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "006 Accuracy, precision, and trueness",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:006",
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
      "ref": "sci-evidence:common:accuracy-precision"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:006",
    "foundation_topic_id": "SCI-COM-006",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "Measurement accuracy and measurement precision are related but are not interchangeable metrology terms.",
    "definitions": [
      "accuracy: agreement considered with trueness and precision",
      "trueness: agreement of a replicate mean with a reference",
      "precision: agreement among replicates under specified conditions"
    ],
    "assumptions": [
      "Vocabulary and manufacturer definition are available."
    ],
    "applicability": {
      "scope": "metrology terminology and explicitly defined specifications"
    },
    "limitations": [
      "An undefined label such as accuracy ±1% is not automatically a violation."
    ],
    "invalid_outside": [
      "manufacturer labels whose definition is unavailable"
    ],
    "related_knowledge": [
      "sci:common:005",
      "sci:common:007"
    ],
    "evidence_refs": [
      "sci-evidence:common:accuracy-precision"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:accuracy-precision",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-006 — Narrow reviewed Foundation statement

Measurement accuracy and measurement precision are related but are not interchangeable metrology terms.

Candidate-only draft; authorized Admin review is absent.
