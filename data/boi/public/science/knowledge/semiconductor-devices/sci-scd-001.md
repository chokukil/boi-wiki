---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-SCD-001 Fermi occupation probability",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:semiconductor-devices:001",
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
      "ref": "sci-evidence:semiconductor-devices:bands-fermi-level"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:semiconductor-devices:001",
    "domain_topic_id": "SCI-SCD-001",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "hypothesis",
    "statement": "The Fermi function f(E) gives the probability that an available state at energy E is occupied by an electron.",
    "assumptions": [
      "All Rule conditions for sci-rule:semiconductor-devices:001 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:semiconductor-devices:001."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:bands-fermi-level"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:bands-fermi-level",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-SCD-001 — Fermi occupation probability

The Fermi function f(E) gives the probability that an available state at energy E is occupied by an electron.

Candidate-only draft; authorized Admin review is absent.
