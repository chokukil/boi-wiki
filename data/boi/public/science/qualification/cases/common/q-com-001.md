---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-001 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:001",
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
      "ref": "sci-rule:common:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:001",
    "standard_id": "Q-COM-001",
    "rule_id": "sci-rule:common:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:001:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:clear_violation",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:6d84e49161e3e52e511757cb35884dd1846b301b5614118ca4fbecf2a4c20afc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 135,
            "exact": "A sample length may be represented by a time unit without changing its scientific meaning. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:in_scope_consistency",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:a0e1e00673b7da4f6c2d215b7c0f91a147d6d2698785bab0d8daba2afa8cfd5f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 127,
            "exact": "A sample length is represented by a quantity whose unit has length dimensionality. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:missing_required_condition",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:83bfd3d69be0613c9717f598bc1d3dec09b7f11b165fb5cefeed04a1fc641c99",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "Without specifying quantity role, the report states that a sample length is represented by a quantity whose unit has length dimensionality. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:outside_validity_domain",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:d3cf358de08b3ef3873dc3308a7e981eba6308b1d5887c4d3b3162477899420e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 198,
            "exact": "In a different scientific context, the report nevertheless states that a sample length is represented by a quantity whose unit has length dimensionality. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:empirical_verification_required",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:7495926995b6d1faf9cdac6ff80ff801c12f9570cf3d35353947cb1c96af35ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 211,
            "exact": "For a named realization, the report asserts that a sample length is represented by a quantity whose unit has length dimensionality. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              },
              {
                "condition_id": "requested_foundation_001_qualified_observation",
                "value": "unqualified_observation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:model"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:negation",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:0438ff79baf7109380374a63a29bab8f91bad83806df86a53b2e31ebe900b515",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 147,
            "exact": "It is not true that a sample length is represented by a quantity whose unit has length dimensionality. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:unit_variation",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:ec4a007c071ebda15e68b1bfc22580204391d8cd2d86d8176a59135a992df761",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 147,
            "exact": "A sample length is represented by a quantity whose unit has length dimensionality. The same sample length is written as 100 centimeter and 1 meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "sample_length_reference",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "sample_length",
            "value": 1,
            "unit": "meter"
          },
          {
            "quantity_kind": "sample_length",
            "value": 100,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:decision_changing_ambiguity",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:05f06567ba831b7844467bc66416d4798da3d8b509a2030ecba048e0687a86b5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 272,
            "exact": "The wording leaves unresolved whether 'A sample length is represented by a quantity whose unit has length dimensionality.' or instead 'A sample length may be represented by a time unit without changing its scientific meaning.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [
              "ambiguity:common:001"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:05f06567ba831b7844467bc66416d4798da3d8b509a2030ecba048e0687a86b5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 272,
            "exact": "The wording leaves unresolved whether 'A sample length is represented by a quantity whose unit has length dimensionality.' or instead 'A sample length may be represented by a time unit without changing its scientific meaning.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [
              "ambiguity:common:001"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:001",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:001:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:paraphrase",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:dccebcdbcc8412e7b9b71ee85810281b3b5e7704c67afcc413854ba7150ebfb3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 175,
            "exact": "In equivalent wording, the document states that a sample length is represented by a quantity whose unit has length dimensionality. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:false_red_prevention",
          "document_ref": "qualification:common:001",
          "document_digest": "sha256:92a052753b5094670475ca96a9b3b408873f0b2fadc9acb7955b2f616390a8bc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 131,
            "exact": "A time interval is not the sample-length quantity covered by this dimensional example. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "time_interval"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-001

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
