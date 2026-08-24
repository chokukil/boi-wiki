---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-ontology-binding",
  "title": "Domain ontology binding: thin-film-property",
  "description": "Interpretation-only agent draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:ontology-binding:domain:thin-film-property",
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
      "ref": "sci-evidence:materials:nist-thin-film-bulk-difference"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "binding_id": "sci:binding:domain:thin-film-property",
    "ontology_release_id": "sci:ontology:general-science-draft/0.1.0",
    "concept_id": "sci:concept:thin-film-property",
    "aliases": [
      "thin-film property",
      "박막 물성"
    ],
    "meaning": "Interpret the listed aliases as sci:concept:thin-film-property while retaining narrower process, state, and model distinctions.",
    "domain": "materials",
    "must_not_collapse": [
      "sci:concept:bulk-property"
    ],
    "interpretation_only": true,
    "relation_provenance": "declared_agent_draft",
    "decision_impact": "interpretation_candidate_only_no_outcome_direction",
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# thin-film-property

This binding helps interpret Korean and English terms. It supplies no scientific outcome, relation direction, or verdict.
