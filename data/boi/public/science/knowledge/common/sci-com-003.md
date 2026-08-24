---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "003 Registered unit conversion kind",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:003",
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
      "ref": "sci-evidence:common:celsius-kelvin"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:003",
    "foundation_topic_id": "SCI-COM-003",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "A unit conversion must use its registered conversion kind; Celsius-to-kelvin absolute readings use an affine offset even though degree Celsius and kelvin intervals have equal magnitude.",
    "definitions": [
      "multiplicative conversion: scale only",
      "affine conversion: scale and offset",
      "logarithmic conversion: registered logarithmic relation",
      "procedure-defined conversion: registered procedure"
    ],
    "assumptions": [
      "Source unit, target unit, and interval-versus-absolute meaning are known."
    ],
    "applicability": {
      "scope": "conversions in the locked Science conversion registry"
    },
    "limitations": [
      "The executable rule demonstrates the Celsius-to-kelvin affine conversion only."
    ],
    "invalid_outside": [
      "unregistered conversions",
      "ambiguous interval-versus-absolute temperature claims"
    ],
    "related_knowledge": [
      "sci:common:001",
      "sci:common:002"
    ],
    "evidence_refs": [
      "sci-evidence:common:celsius-kelvin"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:celsius-kelvin",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-003 — Registered unit conversion kind

A unit conversion must use its registered conversion kind; Celsius-to-kelvin absolute readings use an affine offset even though degree Celsius and kelvin intervals have equal magnitude.

This candidate draft requires authorized Admin review before active decision use.
