---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "012 Correlation does not establish causation",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:012",
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
      "ref": "sci-evidence:common:correlation-causation"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:012",
    "foundation_topic_id": "SCI-COM-012",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "hypothesis",
    "statement": "Correlation does not imply causality, and a broader association is not silently normalized to quantified correlation.",
    "definitions": [
      "association: statistical dependence",
      "correlation: quantified association",
      "causal claim: assertion that changing one factor changes another",
      "confounder: factor that can distort an association"
    ],
    "assumptions": [
      "The evidence basis for the causal claim is identified."
    ],
    "applicability": {
      "scope": "claims inferring causation from observed correlation"
    },
    "limitations": [
      "The rule rejects correlation-only inference; it does not assert causation is absent."
    ],
    "invalid_outside": [
      "claims whose causal evidence is not represented",
      "colloquial non-statistical uses of correlation"
    ],
    "related_knowledge": [
      "sci:common:008",
      "sci:common:011"
    ],
    "evidence_refs": [
      "sci-evidence:common:correlation-causation"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:correlation-causation",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-012 — Narrow reviewed Foundation statement

Correlation does not imply causality, and a broader association is not silently normalized to quantified correlation.

Candidate-only draft; authorized Admin review is absent.
