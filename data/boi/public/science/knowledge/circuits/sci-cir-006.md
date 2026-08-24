---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-CIR-006 Measurement loading",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:circuits:006",
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
      "ref": "sci-evidence:circuits:measurement-loading"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:circuits:006",
    "domain_topic_id": "SCI-CIR-006",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "derived_model",
    "statement": "Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading.",
    "assumptions": [
      "All Rule conditions for sci-rule:circuits:006 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:circuits:006."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:circuits:measurement-loading"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:circuits:measurement-loading",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-CIR-006 — Measurement loading

Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading.

Candidate-only draft; authorized Admin review is absent.
