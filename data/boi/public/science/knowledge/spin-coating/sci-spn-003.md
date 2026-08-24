---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-SPN-003 Evaporation-aware spin-model limits",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:spin-coating:003",
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
      "ref": "sci-evidence:spin-coating:microchemicals-spin-mechanism"
    },
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
    "knowledge_id": "sci:spin-coating:003",
    "domain_topic_id": "SCI-SPN-003",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "hypothesis",
    "statement": "A dry-film spin model must state how solvent evaporation and drying termination enter its validity domain; the inaccessible Meyerhofer abstract is excluded from decision evidence.",
    "assumptions": [
      "All Rule conditions for sci-rule:spin-coating:003 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:spin-coating:003."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:spin-coating:microchemicals-spin-mechanism",
      "sci-evidence:common:model-validity"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-spin-mechanism",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      },
      {
        "evidence_ref": "sci-evidence:common:model-validity",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "excluded_evidence_refs": [
      "sci-evidence:spin-coating:meyerhofer-model"
    ],
    "exclusion_reason": "The cited historical source is inactive because only an access-limited abstract was reviewed; it cannot support a decision."
  }
}
---

# SCI-SPN-003 — Evaporation-aware spin-model limits

A dry-film spin model must state how solvent evaporation and drying termination enter its validity domain; the inaccessible Meyerhofer abstract is excluded from decision evidence.

Candidate-only draft; authorized Admin review is absent.
