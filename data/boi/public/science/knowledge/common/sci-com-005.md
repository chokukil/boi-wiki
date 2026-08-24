---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "005 Measurement uncertainty and error",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:005",
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
      "ref": "sci-evidence:common:uncertainty-error"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:005",
    "foundation_topic_id": "SCI-COM-005",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "Measurement uncertainty and measurement error are different concepts; an uncertainty value is not a known signed deviation from a true quantity value.",
    "definitions": [
      "measurement uncertainty: non-negative parameter characterizing attributed dispersion",
      "measurement error: measured value minus a reference value"
    ],
    "assumptions": [
      "Terms use a resolved metrology vocabulary."
    ],
    "applicability": {
      "scope": "metrology statements distinguishing uncertainty from error"
    },
    "limitations": [
      "The Evidence defines uncertainty only; the contrast remains an Admin-review-required draft."
    ],
    "invalid_outside": [
      "generic process-failure uses of error",
      "unknown local terminology"
    ],
    "related_knowledge": [
      "sci:common:004",
      "sci:common:006"
    ],
    "evidence_refs": [
      "sci-evidence:common:uncertainty-error"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:uncertainty-error",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-005 — Measurement uncertainty and error

Measurement uncertainty and measurement error are different concepts; an uncertainty value is not a known signed deviation from a true quantity value.

This candidate draft requires authorized Admin review before active decision use.
