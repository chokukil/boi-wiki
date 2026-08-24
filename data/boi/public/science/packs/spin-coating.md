---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-pack",
  "title": "spin-coating 0.1.0",
  "description": "Candidate-only domain/application Pack draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:pack:spin-coating-0.1.0",
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
      "ref": "sci:spin-coating:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "name": "spin-coating",
    "version": "0.1.0",
    "dependencies": [
      {
        "relation": "depends_on",
        "ref": "sci-pack:physical-principles/0.1.0"
      },
      {
        "relation": "depends_on",
        "ref": "sci-pack:chemical-principles/0.1.0"
      },
      {
        "relation": "depends_on",
        "ref": "sci-pack:materials-science/0.1.0"
      }
    ],
    "knowledge_refs": [
      "sci:spin-coating:001",
      "sci:spin-coating:002",
      "sci:spin-coating:003",
      "sci:spin-coating:004",
      "sci:spin-coating:005"
    ],
    "rule_refs": [
      "sci-rule:spin-coating:001",
      "sci-rule:spin-coating:002",
      "sci-rule:spin-coating:003",
      "sci-rule:spin-coating:004",
      "sci-rule:spin-coating:005"
    ],
    "qualification_refs": [
      "sci-matrix:spin-coating:001",
      "sci-matrix:spin-coating:002",
      "sci-matrix:spin-coating:003",
      "sci-matrix:spin-coating:004",
      "sci-matrix:spin-coating:005"
    ],
    "ontology_binding_refs": [
      "sci:binding:domain:spin-speed",
      "sci:binding:domain:film-thickness",
      "sci:binding:domain:photoresist"
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

# spin-coating

This draft groups atomic Knowledge, deterministic Rules, interpretation-only bindings, and public qualification cases. It supplies no recipe, numeric operating recommendation, approval, activation, or operational capability.
