---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-SPN-004 Drying-limited spin-speed direction",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:spin-coating:004",
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
      "ref": "sci-evidence:spin-coating:vendor-spin-curve-observation"
    },
    {
      "type": "boi",
      "ref": "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:spin-coating:004",
    "domain_topic_id": "SCI-SPN-004",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "derived_model",
    "statement": "When photoresist spin-off continues until drying stops the flow, attainable resist film thickness decreases approximately with the reciprocal square root of spin speed.",
    "assumptions": [
      "All Rule conditions for sci-rule:spin-coating:004 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:spin-coating:004."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:spin-coating:vendor-spin-curve-observation",
      "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:spin-coating:vendor-spin-curve-observation",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      },
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-SPN-004 Drying-limited spin-speed direction

When photoresist spin-off continues until drying stops the flow, attainable resist film thickness decreases approximately with the reciprocal square root of spin speed.

Candidate-only draft; authorized Admin review is absent.
