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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 309,
            "exact": "Measurement accuracy and measurement precision are interchangeable metrology terms. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nMeasurement accuracy and measurement pr"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 334,
            "end": 503,
            "exact": "Measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "ccuracy assessment error = 0.001 meter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying terminology co"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 534,
            "end": 766,
            "exact": "Without specifying terminology context, the report states that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "y assessment error = 0.001 meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 794,
            "end": 1034,
            "exact": "In a different scientific context, the report nevertheless states that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "racy assessment error = 0.001 meter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1070,
            "end": 1323,
            "exact": "For a named realization, the report asserts that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. No qualified observation is bound. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "essment error = 0.001 meter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that measurement accuracy and measur"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1336,
            "end": 1525,
            "exact": "It is not true that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "uantity is accuracy assessment error = 0.001 meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nMeasurement accuracy and measurement precisio"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1544,
            "end": 1770,
            "exact": "Measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The reviewed quantities are accuracy assessment error = 0.1 centimeter; accuracy assessment error reference = 0.001 meter.",
            "prefix": "y is accuracy assessment error = 0.001 meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1802,
            "end": 2041,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Measurement accuracy and measurement precision are related but are not interchangeable metrology terms”. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "t error reference = 0.001 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that m"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1802,
            "end": 2041,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Measurement accuracy and measurement precision are related but are not interchangeable metrology terms”. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "t error reference = 0.001 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that m"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2056,
            "end": 2273,
            "exact": "In equivalent wording, the document states that measurement accuracy and measurement precision are related but are not interchangeable metrology terms. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "ntity is accuracy assessment error = 0.001 meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA colloquial vendor label is not the re"
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
          "document_ref": "qualification-fixture:common:006",
          "document_digest": "sha256:2b9ca1de17e5dba2cd0bd38f084296748217380d2a31ce0a249ac4791be51ab8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2298,
            "end": 2443,
            "exact": "A colloquial vendor label is not the resolved metrology terminology comparison. The reviewed quantity is accuracy assessment error = 0.001 meter.",
            "prefix": "ccuracy assessment error = 0.001 meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
