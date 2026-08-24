---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-PHY-002 External force changes system momentum",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:physics:002",
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
      "ref": "sci-evidence:physics:force-momentum"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:physics:002",
    "standard_id": "R-PHY-002",
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:external-force",
      "sci:concept:system-momentum"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:external-force",
    "object_concept_id": "sci:concept:system-momentum",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "system_boundary",
        "operator": "eq",
        "value": "explicit_closed_system"
      },
      {
        "key": "net_external_force",
        "operator": "eq",
        "value": "resolved_nonzero_vector"
      }
    ],
    "validity_conditions": [
      {
        "key": "reference_frame",
        "operator": "eq",
        "value": "inertial"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_momentum_response_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "net_force": "newton"
    },
    "knowledge_refs": [
      "sci:physics:002"
    ],
    "evidence_refs": [
      "sci-evidence:physics:force-momentum"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:physics:force-momentum",
        "claim_family": "locator_bound.physics.force_momentum",
        "purpose": "We conclude that the external force causes the momentum of the system to change, and we thus restate and generalize Newton’s Second Law for a system of objects as"
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "changes",
    "contradiction_predicates": [
      "cannot_change"
    ],
    "expected_polarity": "positive",
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "net_force",
        "quantity_kind": "net_force",
        "reference_quantity_kind": "net_force_reference"
      }
    ]
  }
}
---
# R-PHY-002 — External force changes system momentum

Closed evaluator: `directional_relation`. Candidate qualification only.
