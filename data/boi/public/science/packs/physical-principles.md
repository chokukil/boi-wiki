---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-pack",
  "title": "physical-principles 0.1.0",
  "description": "Candidate-only domain/application Pack draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:pack:physical-principles-0.1.0",
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
      "ref": "sci:physics:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "name": "physical-principles",
    "version": "0.1.0",
    "dependencies": [
      {
        "relation": "depends_on",
        "ref": "sci-pack:science-foundation/0.1.0"
      }
    ],
    "knowledge_refs": [
      "sci:physics:001",
      "sci:physics:002",
      "sci:physics:003",
      "sci:physics:004",
      "sci:physics:005"
    ],
    "rule_refs": [
      "sci-rule:physics:001",
      "sci-rule:physics:002",
      "sci-rule:physics:003",
      "sci-rule:physics:004",
      "sci-rule:physics:005"
    ],
    "qualification_refs": [
      "sci-matrix:physics:001",
      "sci-matrix:physics:002",
      "sci-matrix:physics:003",
      "sci-matrix:physics:004",
      "sci-matrix:physics:005"
    ],
    "ontology_binding_refs": [
      "sci:binding:domain:angular-speed",
      "sci:binding:domain:viscosity"
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

# physical-principles

This draft groups atomic Knowledge, deterministic Rules, interpretation-only bindings, and public qualification cases. It supplies no recipe, numeric operating recommendation, approval, activation, or operational capability.
