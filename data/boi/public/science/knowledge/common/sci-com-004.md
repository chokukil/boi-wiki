---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "004 Measurand and measurement result",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:004",
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
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:004",
    "foundation_topic_id": "SCI-COM-004",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty.",
    "definitions": [
      "measurand: quantity intended to be measured",
      "measurement result: reported measured value with accompanying information",
      "influence quantity: quantity affecting indication and result"
    ],
    "assumptions": [
      "The comparison concerns a measurement result rather than a nominal setting."
    ],
    "applicability": {
      "scope": "measurement-result comparisons"
    },
    "limitations": [
      "The rule checks context presence, not instrument fitness or traceability."
    ],
    "invalid_outside": [
      "nominal recipe values presented as measurements",
      "comparisons without an identifiable measurand"
    ],
    "related_knowledge": [
      "sci:common:005",
      "sci:common:007"
    ],
    "evidence_refs": [
      "sci-evidence:common:measurand-result"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:measurand-result",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-004 — Narrow reviewed Foundation statement

A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty.

Candidate-only draft; authorized Admin review is absent.
