---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-pack",
  "title": "circuit-principles 0.1.0",
  "description": "Candidate-only domain/application Pack draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:pack:circuit-principles-0.1.0",
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
      "ref": "sci:circuits:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "name": "circuit-principles",
    "version": "0.1.0",
    "dependencies": [
      {
        "relation": "depends_on",
        "ref": "sci-pack:science-foundation/0.1.0"
      }
    ],
    "knowledge_refs": [
      "sci:circuits:001",
      "sci:circuits:002",
      "sci:circuits:003",
      "sci:circuits:004",
      "sci:circuits:005",
      "sci:circuits:006"
    ],
    "rule_refs": [
      "sci-rule:circuits:001",
      "sci-rule:circuits:002",
      "sci-rule:circuits:003",
      "sci-rule:circuits:004",
      "sci-rule:circuits:005",
      "sci-rule:circuits:006"
    ],
    "qualification_refs": [
      "sci-matrix:circuits:001",
      "sci-matrix:circuits:002",
      "sci-matrix:circuits:003",
      "sci-matrix:circuits:004",
      "sci-matrix:circuits:005",
      "sci-matrix:circuits:006"
    ],
    "ontology_binding_refs": [
      "sci:binding:domain:resistance",
      "sci:binding:domain:electric-power"
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

# circuit-principles

This draft groups atomic Knowledge, deterministic Rules, interpretation-only bindings, and public qualification cases. It supplies no recipe, numeric operating recommendation, approval, activation, or operational capability.
