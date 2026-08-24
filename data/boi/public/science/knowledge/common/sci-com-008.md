---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "008 Model assumptions and validity domain",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:008",
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
    "knowledge_id": "sci:common:008",
    "foundation_topic_id": "SCI-COM-008",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "model",
    "assurance_basis": "hypothesis",
    "statement": "A model supports a proposed use only within a recorded validation domain and with its assumptions and limitations addressed; a fit statistic alone does not establish universal truth.",
    "definitions": [
      "model basis: theoretical, semi-empirical, or empirical fit",
      "validation domain: recorded range and conditions of validation evidence",
      "extrapolation: use outside that domain"
    ],
    "assumptions": [
      "Model identity, basis, intended use, and validation record are known."
    ],
    "applicability": {
      "scope": "claims that a model is valid for an intended use"
    },
    "limitations": [
      "Candidate qualification uses explicit synthetic observation fixtures; no operational approval is asserted."
    ],
    "invalid_outside": [
      "unidentified models",
      "uses outside an unresolved validation domain"
    ],
    "related_knowledge": [
      "sci:common:002",
      "sci:common:011"
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

# SCI-COM-008 — Model assumptions and validity domain

A model supports a proposed use only within a recorded validation domain and with its assumptions and limitations addressed; a fit statistic alone does not establish universal truth.

This candidate draft requires authorized Admin review before active decision use.
