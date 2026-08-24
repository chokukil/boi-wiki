---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-006 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:006",
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
      "ref": "sci-rule:common:006"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:006",
    "standard_id": "Q-COM-006",
    "rule_id": "sci-rule:common:006",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:006:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:clear_violation",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:512fde5b66f12c85efbf50b2eee41d78f98de82fcc5363a04ed9d3622a2f69d9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 128,
            "exact": "Measurement accuracy and measurement precision are interchangeable metrology terms. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "interchangeable_with",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:in_scope_consistency",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:7076ff14d6f6fe5b82906476a0301b6b59f219459fe275f46485c21144777057",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 148,
            "exact": "Measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:missing_required_condition",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:9c37d5bcde8c902eaf67763764bfd41f799bafc1626babd1c88fbcf9caf19176",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 211,
            "exact": "Without specifying terminology context, the report states that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:outside_validity_domain",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:46e4d4996206957681d88eaf73a49a6dd50d57e57a00f732fc98943d8e5232b0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 219,
            "exact": "In a different scientific context, the report nevertheless states that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:empirical_verification_required",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:2d17f41bfd3d681d70da10fa0a9c037353fdd62167755c2ecf2c5eb9890ef10e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 232,
            "exact": "For a named realization, the report asserts that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              },
              {
                "condition_id": "requested_foundation_006_qualified_observation",
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
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:negation",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:278d925540fa6abb0af5e697cd63fd5703ffb13660a3810201cdd5ad146783f8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 168,
            "exact": "It is not true that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:unit_variation",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:9ad44c5e1954156e596d56ac96352fde4b8ce320368ab8e8eef6a60653a57669",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "Measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The same accuracy assessment error is written as 0.1 centimeter and 0.001 meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.1,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "accuracy_assessment_error_reference",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "accuracy_assessment_error",
            "value": 0.001,
            "unit": "meter"
          },
          {
            "quantity_kind": "accuracy_assessment_error",
            "value": 0.1,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:decision_changing_ambiguity",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:50acbf806f38b433959ab3da9c0e631a60b62b7560bf725b0dba29c677bb9736",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 286,
            "exact": "The wording leaves unresolved whether 'Measurement accuracy and measurement precision are related but are not interchangeable metrology terms.' or instead 'Measurement accuracy and measurement precision are interchangeable metrology terms.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [
              "ambiguity:common:006"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:006:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:50acbf806f38b433959ab3da9c0e631a60b62b7560bf725b0dba29c677bb9736",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 286,
            "exact": "The wording leaves unresolved whether 'Measurement accuracy and measurement precision are related but are not interchangeable metrology terms.' or instead 'Measurement accuracy and measurement precision are interchangeable metrology terms.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "interchangeable_with",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [
              "ambiguity:common:006"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:006",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:006:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:paraphrase",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:ce61be8657167e4e82c526f1ce1ee2ab2c96fd69d98a0783e2b276855b77fe52",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 196,
            "exact": "In equivalent wording, the document states that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "metrology"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      },
      {
        "case_id": "sci-case:common:006:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:006",
        "claim_packet": {
          "claim_id": "claim:common:006:false_red_prevention",
          "document_ref": "qualification:common:006",
          "document_digest": "sha256:b222828c728b837d5585fcb4c10cb1075ff9184a5893fdbf1a93575e9276e2f0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 124,
            "exact": "A colloquial vendor label is not the resolved metrology terminology comparison. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-accuracy",
            "relation_kind": "empirical_relation",
            "predicate": "interchangeable_with",
            "object_concept_id": "sci:concept:measurement-precision",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "accuracy_assessment_error",
                "value": 0.001,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "terminology_context",
                "value": "colloquial_vendor_label"
              },
              {
                "condition_id": "manufacturer_term_definition",
                "value": "resolved"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:accuracy",
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:accuracy-precision"
        ],
        "matrix_rule_id": "sci-rule:common:006"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-006

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
