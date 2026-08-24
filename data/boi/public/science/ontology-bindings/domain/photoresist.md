---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-ontology-binding",
  "title": "Domain ontology binding: photoresist",
  "description": "Interpretation-only agent draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:ontology-binding:domain:photoresist",
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
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "binding_id": "sci:binding:domain:photoresist",
    "ontology_release_id": "sci:ontology:general-science-draft/0.1.0",
    "concept_id": "sci:concept:photoresist",
    "aliases": [
      "photoresist",
      "resist",
      "포토레지스트"
    ],
    "meaning": "Interpret the listed aliases as sci:concept:photoresist while retaining narrower process, state, and model distinctions.",
    "domain": "spin-coating",
    "must_not_collapse": [
      "sci:concept:solvent"
    ],
    "interpretation_only": true,
    "relation_provenance": "declared_agent_draft",
    "decision_impact": "interpretation_candidate_only_no_outcome_direction",
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# photoresist

This binding helps interpret Korean and English terms. It supplies no scientific outcome, relation direction, or verdict.
