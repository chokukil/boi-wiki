---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-MAT-005 Bulk properties do not automatically transfer to thin films",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:materials:005",
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
    "rule_id": "sci-rule:materials:005",
    "standard_id": "R-MAT-005",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:bulk-property-transfer",
      "sci:concept:thin-film-property"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:bulk-property-transfer",
    "object_concept_id": "sci:concept:thin-film-property",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "property_class",
        "operator": "eq",
        "value": "mechanical"
      },
      {
        "key": "material_form",
        "operator": "eq",
        "value": "thin_film"
      },
      {
        "key": "comparison_composition",
        "operator": "eq",
        "value": "same"
      }
    ],
    "validity_conditions": [
      {
        "key": "film_origin",
        "operator": "eq",
        "value": "deposition_defined"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "claim_specificity",
        "operator": "eq",
        "value": "equipment_or_numeric"
      }
    ],
    "context_dimensions": {
      "film_thickness_scale": "nanometer"
    },
    "knowledge_refs": [
      "sci:materials:005"
    ],
    "evidence_refs": [
      "sci-evidence:materials:nist-thin-film-bulk-difference"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:materials:nist-thin-film-bulk-difference",
        "claim_family": "materials.thin_film_bulk_property_nontransferability",
        "purpose": "Mechanical properties of thin films can differ from bulk material of the same chemical composition because deposition conditions differ."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "not_automatically_transferable",
    "contradiction_predicates": [
      "automatically_equal"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-MAT-005 — Bulk properties do not automatically transfer to thin films

Closed evaluator: `directional_relation`. Candidate qualification only.
