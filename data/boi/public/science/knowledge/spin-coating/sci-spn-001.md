---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-SPN-001 Spin-film measurement state",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:spin-coating:001",
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
    },
    {
      "type": "boi",
      "ref": "sci-evidence:spin-coating:microchemicals-film-state-change"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:spin-coating:001",
    "domain_topic_id": "SCI-SPN-001",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "hypothesis",
    "statement": "A spin-coated film-thickness result must identify the process and measurement state and report uncertainty before wet, post-spin, and post-bake values are compared.",
    "assumptions": [
      "All Rule conditions for sci-rule:spin-coating:001 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:spin-coating:001."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:common:measurand-result",
      "sci-evidence:spin-coating:microchemicals-film-state-change"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:measurand-result",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      },
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-film-state-change",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-SPN-001 — Spin-film measurement state

A spin-coated film-thickness result must identify the process and measurement state and report uncertainty before wet, post-spin, and post-bake values are compared.

Candidate-only draft; authorized Admin review is absent.
