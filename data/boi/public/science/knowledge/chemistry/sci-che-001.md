---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-CHE-001 Molar concentration definition",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:chemistry:001",
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
      "ref": "sci-evidence:chemistry:amount-concentration"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:chemistry:001",
    "domain_topic_id": "SCI-CHE-001",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "knowledge_kind": "model",
    "assurance_basis": "derived_model",
    "statement": "Molar concentration is the amount of solute in moles divided by the solution volume in litres for the stated molarity convention.",
    "assumptions": [
      "All Rule conditions for sci-rule:chemistry:001 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:chemistry:001."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:chemistry:amount-concentration"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:chemistry:amount-concentration",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-CHE-001 — Molar concentration definition

Molar concentration is the amount of solute in moles divided by the solution volume in litres for the stated molarity convention.

Candidate-only draft; authorized Admin review is absent.
