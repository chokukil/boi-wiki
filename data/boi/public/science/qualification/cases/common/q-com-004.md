---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-004 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:004",
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
      "ref": "sci-rule:common:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:004",
    "standard_id": "Q-COM-004",
    "rule_id": "sci-rule:common:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:004:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:clear_violation",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:20b6c5271a951ee0530dfbb5a4369ec02f8cffdb0f6775e384f71b1212bd6829",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 149,
            "exact": "A measurement result is generally complete without a measured quantity value or measurement uncertainty. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:in_scope_consistency",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:9aed29c71f83bcd790a56cb9d4f02f197fae9a47c13003f00697dd765bf7dd6f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 158,
            "exact": "A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:missing_required_condition",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:fbfe1d00e26d348f70963b2059a353604526293492afb74f448bd3138ae10b9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 230,
            "exact": "Without specifying result expression components, the report states that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:outside_validity_domain",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:2cbd03181f26e2b204fcdcac51bb9a7e1fa755add805df3ce4f65ca303058749",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "In a different scientific context, the report nevertheless states that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:empirical_verification_required",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:e3231fb384ee3166890b58119cc5a98f1fd8108aaeebdfddc7fcf203c3533a30",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 242,
            "exact": "For a named realization, the report asserts that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              },
              {
                "condition_id": "requested_foundation_004_qualified_observation",
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
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:negation",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:44528ed19ebcdfa6e96b556043876db4fbffce7002f99db91e4be2a8b2877dcb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 178,
            "exact": "It is not true that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:unit_variation",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:76f01905c49e813a4f2d0738e754977c06b92f214182d56852e4eef843ca06a1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The same measured quantity value is written as 100 centimeter and 1 meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "measured_quantity_value_reference",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "measured_quantity_value",
            "value": 1,
            "unit": "meter"
          },
          {
            "quantity_kind": "measured_quantity_value",
            "value": 100,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:decision_changing_ambiguity",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:4cb5b0cd9225588fc7d82553eebb7f16106e6cb69d324745e382a627fe2153b0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 317,
            "exact": "The wording leaves unresolved whether 'A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty.' or instead 'A measurement result is generally complete without a measured quantity value or measurement uncertainty.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [
              "ambiguity:common:004"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:4cb5b0cd9225588fc7d82553eebb7f16106e6cb69d324745e382a627fe2153b0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 317,
            "exact": "The wording leaves unresolved whether 'A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty.' or instead 'A measurement result is generally complete without a measured quantity value or measurement uncertainty.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [
              "ambiguity:common:004"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:004",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:004:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:paraphrase",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:98ac50bc37514fa29cd4dd933c556c5f290e93e963d9e0d194b74dcb64d6fbc3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 206,
            "exact": "In equivalent wording, the document states that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "measured_value_and_uncertainty"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      },
      {
        "case_id": "sci-case:common:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:false_red_prevention",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:1550381f78e6fe559b136b6b6e2c9743fb1e59f9f469a331230322afda0d999f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 151,
            "exact": "A quantity value written without uncertainty does not satisfy this reviewed measurement-result expression. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result-expression",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:value-and-uncertainty",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "measured_quantity_value",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "result_expression_components",
                "value": "value_only"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_result"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "matrix_rule_id": "sci-rule:common:004"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-004

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
