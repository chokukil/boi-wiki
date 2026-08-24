---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-MAT-003 Metastable phases can transform",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:materials:003",
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
      "ref": "sci-evidence:materials:phase-transformation"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:materials:003",
    "domain_topic_id": "SCI-MAT-003",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "derived_model",
    "statement": "A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available.",
    "assumptions": [
      "All Rule conditions for sci-rule:materials:003 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:materials:003."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:materials:phase-transformation"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:materials:phase-transformation",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-MAT-003 — Metastable phases can transform

A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available.

Candidate-only draft; authorized Admin review is absent.
