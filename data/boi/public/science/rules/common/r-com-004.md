---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-004 Measurand and measurement result",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:004",
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
      "ref": "sci-evidence:common:measurand-result"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:004",
    "standard_id": "R-COM-004",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:measurement-result",
      "sci:concept:measurand"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:measurement-result",
    "object_concept_id": "sci:concept:measurand",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "measurand_defined",
        "operator": "eq",
        "value": true
      },
      {
        "key": "measurement_conditions_defined",
        "operator": "eq",
        "value": true
      }
    ],
    "validity_conditions": [
      {
        "key": "measurement_procedure_scope",
        "operator": "eq",
        "value": "documented"
      }
    ],
    "knowledge_refs": [
      "sci:common:004"
    ],
    "evidence_refs": [
      "sci-evidence:common:measurand-result"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:measurand-result",
        "claim_family": "locator_bound.common.measurand_result",
        "purpose": "A measurement result is generally expressed as a single measured quantity value and a measurement uncertainty."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-COM-004 — Measurand and measurement result

Closed evaluator: `validity_domain`. Candidate qualification only.
