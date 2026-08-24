---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "010 Steady state and equilibrium",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:knowledge:common:010",
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
      "ref": "sci-evidence:common:steady-state"
    },
    {
      "type": "boi",
      "ref": "sci-evidence:common:equilibrium"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:common:010",
    "foundation_topic_id": "SCI-COM-010",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "knowledge_kind": "definition",
    "assurance_basis": "hypothesis",
    "statement": "Steady state means time independent in the cited diffusion context, while dynamic equilibrium has equal forward and reverse reaction rates and no net composition change.",
    "definitions": [
      "steady state: selected state variables do not change with time",
      "equilibrium: no net driving tendency for the specified process",
      "dynamic equilibrium: equal opposing rates with no net composition change",
      "nonequilibrium steady state: time-independent state sustained by driving"
    ],
    "assumptions": [
      "State variables and the process for which equilibrium is claimed are identified."
    ],
    "applicability": {
      "scope": "claims comparing steady state with equilibrium"
    },
    "limitations": [
      "The Evidence spans illustrate diffusion steady state and chemical dynamic equilibrium, not every equilibrium notion."
    ],
    "invalid_outside": [
      "claims with no stated variables",
      "stable used as an undefined synonym"
    ],
    "related_knowledge": [
      "sci:common:008",
      "sci:common:009"
    ],
    "evidence_refs": [
      "sci-evidence:common:steady-state",
      "sci-evidence:common:equilibrium"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:common:steady-state",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      },
      {
        "evidence_ref": "sci-evidence:common:equilibrium",
        "role": "locator_bound_support",
        "scope_note": "Limited to the embedded Evidence claim scope and contextual limitations."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# SCI-COM-010 — Narrow reviewed Foundation statement

Steady state means time independent in the cited diffusion context, while dynamic equilibrium has equal forward and reverse reaction rates and no net composition change.

Candidate-only draft; authorized Admin review is absent.
