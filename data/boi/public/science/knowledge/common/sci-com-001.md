---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "001 Quantity, value, unit, and dimension",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:001",
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
    "knowledge_id": "sci:common:001",
    "foundation_topic_id": "SCI-COM-001",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "This executable example checks that a sample-length quantity is represented with length dimensionality; it is not a universal equation solver.",
    "definitions": [
      "quantity: a property represented by a number and a reference",
      "quantity value: the number-reference pair expressing a quantity",
      "measurement unit: the scalar reference used for comparison",
      "dimension: dependence on base quantities"
    ],
    "assumptions": [
      "The quantity kind is identified before unit checking."
    ],
    "applicability": {
      "scope": "scientific quantity statements with an identified quantity kind"
    },
    "limitations": [
      "This check does not establish that a measured value is true."
    ],
    "invalid_outside": [
      "claims whose quantity kind is unresolved"
    ],
    "related_knowledge": [
      "sci:common:002",
      "sci:common:003"
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

# SCI-COM-001 — Narrow reviewed Foundation statement

This executable example checks that a sample-length quantity is represented with length dimensionality; it is not a universal equation solver.

Candidate-only draft; authorized Admin review is absent.
