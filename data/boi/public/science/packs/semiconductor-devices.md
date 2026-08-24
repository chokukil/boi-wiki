---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-pack",
  "title": "semiconductor-devices 0.1.0",
  "description": "Candidate-only domain/application Pack draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:pack:semiconductor-devices-0.1.0",
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
      "ref": "sci:semiconductor-devices:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "name": "semiconductor-devices",
    "version": "0.1.0",
    "dependencies": [
      {
        "relation": "depends_on",
        "ref": "sci-pack:materials-science/0.1.0"
      }
    ],
    "knowledge_refs": [
      "sci:semiconductor-devices:001",
      "sci:semiconductor-devices:002",
      "sci:semiconductor-devices:003",
      "sci:semiconductor-devices:004",
      "sci:semiconductor-devices:005",
      "sci:semiconductor-devices:006"
    ],
    "rule_refs": [
      "sci-rule:semiconductor-devices:001",
      "sci-rule:semiconductor-devices:002",
      "sci-rule:semiconductor-devices:003",
      "sci-rule:semiconductor-devices:004",
      "sci-rule:semiconductor-devices:005",
      "sci-rule:semiconductor-devices:006"
    ],
    "qualification_refs": [
      "sci-matrix:semiconductor-devices:001",
      "sci-matrix:semiconductor-devices:002",
      "sci-matrix:semiconductor-devices:003",
      "sci-matrix:semiconductor-devices:004",
      "sci-matrix:semiconductor-devices:005",
      "sci-matrix:semiconductor-devices:006"
    ],
    "ontology_binding_refs": [
      "sci:binding:domain:semiconductor",
      "sci:binding:domain:mobility",
      "sci:binding:domain:conductivity"
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

# semiconductor-devices

This draft groups atomic Knowledge, deterministic Rules, interpretation-only bindings, and public qualification cases. It supplies no recipe, numeric operating recommendation, approval, activation, or operational capability.
