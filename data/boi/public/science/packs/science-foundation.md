---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-pack",
  "title": "General Science Foundation 0.1.0",
  "description": "Candidate-only General Science Foundation draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:pack:science-foundation-0.1.0",
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
      "ref": "sci:common:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "name": "science-foundation",
    "version": "0.1.0",
    "dependencies": [],
    "knowledge_refs": [
      "sci:common:001",
      "sci:common:002",
      "sci:common:003",
      "sci:common:004",
      "sci:common:005",
      "sci:common:006",
      "sci:common:007",
      "sci:common:008",
      "sci:common:009",
      "sci:common:010",
      "sci:common:011",
      "sci:common:012"
    ],
    "rule_refs": [
      "sci-rule:common:001",
      "sci-rule:common:002",
      "sci-rule:common:003",
      "sci-rule:common:004",
      "sci-rule:common:005",
      "sci-rule:common:006",
      "sci-rule:common:007",
      "sci-rule:common:008",
      "sci-rule:common:009",
      "sci-rule:common:010",
      "sci-rule:common:011",
      "sci-rule:common:012"
    ],
    "qualification_refs": [
      "sci-matrix:common:001",
      "sci-matrix:common:002",
      "sci-matrix:common:003",
      "sci-matrix:common:004",
      "sci-matrix:common:005",
      "sci-matrix:common:006",
      "sci-matrix:common:007",
      "sci-matrix:common:008",
      "sci-matrix:common:009",
      "sci-matrix:common:010",
      "sci-matrix:common:011",
      "sci-matrix:common:012"
    ],
    "ontology_binding_refs": [
      "sci:binding:common:quantity",
      "sci:binding:common:unit",
      "sci:binding:common:dimension",
      "sci:binding:common:measurement-error",
      "sci:binding:common:measurement-uncertainty",
      "sci:binding:common:accuracy",
      "sci:binding:common:precision",
      "sci:binding:common:model",
      "sci:binding:common:steady-state",
      "sci:binding:common:equilibrium",
      "sci:binding:common:association",
      "sci:binding:common:correlation",
      "sci:binding:common:causation"
    ],
    "qualification_mode": "candidate_only",
    "activation_blockers": [
      "authorized Admin reviews absent",
      "release activation absent"
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "executable_coverage": "narrow_reviewed_examples",
    "coverage_limitations": [
      "R-COM-001 covers only a sample-length dimensional example.",
      "R-COM-002 covers only equality between two length terms.",
      "Other quantity kinds, products, quotients, and arbitrary equation structures require additional reviewed Rules."
    ]
  }
}
---
# General Science Foundation

This draft pack groups twelve common scientific-reasoning Knowledge objects, deterministic Rules, interpretation-only ontology bindings, and 120 public qualification cases. It is not an active Science Release.
