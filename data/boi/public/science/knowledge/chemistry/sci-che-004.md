---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-CHE-004 Reaction quotient at equilibrium",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:chemistry:004",
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
      "ref": "sci-evidence:chemistry:reaction-equilibrium"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:chemistry:004",
    "domain_topic_id": "SCI-CHE-004",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "knowledge_kind": "model",
    "assurance_basis": "derived_model",
    "statement": "For the balanced reaction with defined activities at equilibrium, the reaction quotient Q equals the equilibrium constant K.",
    "assumptions": [
      "All Rule conditions for sci-rule:chemistry:004 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:chemistry:004."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:chemistry:reaction-equilibrium"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:chemistry:reaction-equilibrium",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-CHE-004 — Reaction quotient at equilibrium

For the balanced reaction with defined activities at equilibrium, the reaction quotient Q equals the equilibrium constant K.

Candidate-only draft; authorized Admin review is absent.
