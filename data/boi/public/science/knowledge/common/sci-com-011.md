---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "011 Controlled directional claim",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:011",
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
      "ref": "sci-evidence:common:model-validity"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:011",
    "foundation_topic_id": "SCI-COM-011",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "hypothesis",
    "statement": "A model-validation record is a record of the validation domain; this narrow rule does not infer additional process metadata from the one-sentence requirement.",
    "definitions": [
      "controlled variable: variable held fixed for comparison",
      "conditional relation: relation bounded by declared conditions",
      "regime transition: boundary where relation form may change"
    ],
    "assumptions": [
      "Ontology interpretation does not supply an outcome direction."
    ],
    "applicability": {
      "scope": "monotonic or functional directional claims"
    },
    "limitations": [
      "This structural rule does not decide whether a domain outcome increases or decreases."
    ],
    "invalid_outside": [
      "bare influences edges",
      "claims missing comparison basis or valid range"
    ],
    "related_knowledge": [
      "sci:common:008",
      "sci:common:012"
    ],
    "evidence_refs": [
      "sci-evidence:common:model-validity"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:model-validity",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-011 — Narrow reviewed Foundation statement

A model-validation record is a record of the validation domain; this narrow rule does not infer additional process metadata from the one-sentence requirement.

Candidate-only draft; authorized Admin review is absent.
