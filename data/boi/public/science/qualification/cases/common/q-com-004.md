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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 365,
            "exact": "A measurement result is generally complete without a measured quantity value or measurement uncertainty. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA measurement result is generally expre"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 390,
            "end": 604,
            "exact": "A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "; measurement uncertainty = 0.01 meter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying result express"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 635,
            "end": 921,
            "exact": "Without specifying result expression components, the report states that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "urement uncertainty = 0.01 meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [],
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 949,
            "end": 1234,
            "exact": "In a different scientific context, the report nevertheless states that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "easurement uncertainty = 0.01 meter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1270,
            "end": 1568,
            "exact": "For a named realization, the report asserts that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. No qualified observation is bound. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "nt uncertainty = 0.01 meter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a measurement result is general"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1581,
            "end": 1815,
            "exact": "It is not true that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "ue = 1 meter; measurement uncertainty = 0.01 meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA measurement result is generally expressed a"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1834,
            "end": 2100,
            "exact": "A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The reviewed quantities are measured quantity value = 100 centimeter; measured quantity value reference = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": " meter; measurement uncertainty = 0.01 meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2132,
            "end": 2416,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty”. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "rement uncertainty = 0.01 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2132,
            "end": 2416,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A measurement result is generally expressed as a measured quantity value together with a measurement uncertainty”. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "rement uncertainty = 0.01 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2431,
            "end": 2693,
            "exact": "In equivalent wording, the document states that a measurement result is generally expressed as a measured quantity value together with a measurement uncertainty. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": " = 1 meter; measurement uncertainty = 0.01 meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA calibration note lists a measured val"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
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
          "document_ref": "qualification-fixture:common:004",
          "document_digest": "sha256:89d4d4c29393fa54bff6d4c47e3076091dcf6a33708e1675cec5b0c295252b41",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2718,
            "end": 2950,
            "exact": "A calibration note lists a measured value and a standard-deviation estimate, but does not present them as a VIM measurement result. The reviewed quantities are measured quantity value = 1 meter; measurement uncertainty = 0.01 meter.",
            "prefix": "; measurement uncertainty = 0.01 meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
              },
              {
                "quantity_kind": "measurement_uncertainty",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "calibration_note"
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
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-004

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
