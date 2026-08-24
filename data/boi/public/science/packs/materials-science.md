---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-pack",
  "title": "materials-science 0.1.0",
  "description": "Candidate-only domain/application Pack draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:pack:materials-science-0.1.0",
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
      "ref": "sci:materials:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "pack_id": "sci-pack:materials-science/0.1.0",
    "name": "materials-science",
    "version": "0.1.0",
    "dependencies": [
      {
        "relation": "depends_on",
        "ref": "sci-pack:science-foundation/0.1.0"
      }
    ],
    "knowledge_refs": [
      "sci:materials:001",
      "sci:materials:002",
      "sci:materials:003",
      "sci:materials:004",
      "sci:materials:005"
    ],
    "rule_refs": [
      "sci-rule:materials:001",
      "sci-rule:materials:002",
      "sci-rule:materials:003",
      "sci-rule:materials:004",
      "sci-rule:materials:005"
    ],
    "qualification_refs": [
      "sci-matrix:materials:001",
      "sci-matrix:materials:002",
      "sci-matrix:materials:003",
      "sci-matrix:materials:004",
      "sci-matrix:materials:005"
    ],
    "ontology_binding_refs": [
      "sci:binding:domain:bulk-property",
      "sci:binding:domain:thin-film-property"
    ],
    "qualification_mode": "candidate_only",
    "activation_blockers": [
      "authorized Admin reviews absent",
      "release activation absent"
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# materials-science

This draft groups atomic Knowledge, deterministic Rules, interpretation-only bindings, and public qualification cases. It supplies no recipe, numeric operating recommendation, approval, activation, or operational capability.
