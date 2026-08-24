---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-ontology-binding",
  "title": "Domain ontology binding: resistance",
  "description": "Interpretation-only agent draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:ontology-binding:domain:resistance",
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
      "ref": "sci-evidence:circuits:ohm-model"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "binding_id": "sci:binding:domain:resistance",
    "ontology_release_id": "sci:ontology:general-science-draft/0.1.0",
    "concept_id": "sci:concept:resistance",
    "aliases": [
      "resistance",
      "R",
      "저항"
    ],
    "meaning": "Interpret the listed aliases as sci:concept:resistance while retaining narrower process, state, and model distinctions.",
    "domain": "circuits",
    "must_not_collapse": [
      "sci:concept:resistivity"
    ],
    "interpretation_only": true,
    "relation_provenance": "declared_agent_draft",
    "decision_impact": "interpretation_candidate_only_no_outcome_direction",
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# resistance

This binding helps interpret Korean and English terms. It supplies no scientific outcome, relation direction, or verdict.
