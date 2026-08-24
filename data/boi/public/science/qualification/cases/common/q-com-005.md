---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-005 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:005",
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
      "ref": "sci-rule:common:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:005",
    "standard_id": "Q-COM-005",
    "rule_id": "sci-rule:common:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:005:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:clear_violation",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 325,
            "exact": "Measurement uncertainty is not a non-negative dispersion parameter for values attributed to a measurand. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nMeasurement uncertainty is a non-negati"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:in_scope_consistency",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 350,
            "end": 525,
            "exact": "Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": " is uncertainty parameter = 0.01 meter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying parameter sign"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:missing_required_condition",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 556,
            "end": 789,
            "exact": "Without specifying parameter sign, the report states that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "certainty parameter = 0.01 meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
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
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:outside_validity_domain",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 817,
            "end": 1063,
            "exact": "In a different scientific context, the report nevertheless states that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": " uncertainty parameter = 0.01 meter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
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
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:empirical_verification_required",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1099,
            "end": 1358,
            "exact": "For a named realization, the report asserts that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. No qualified observation is bound. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "inty parameter = 0.01 meter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that measurement uncertainty is a no"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              },
              {
                "condition_id": "requested_foundation_005_qualified_observation",
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
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:negation",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1371,
            "end": 1566,
            "exact": "It is not true that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "wed quantity is uncertainty parameter = 0.01 meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nMeasurement uncertainty is a non-negative par"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:unit_variation",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1585,
            "end": 1811,
            "exact": "Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The reviewed quantities are uncertainty parameter = 1 centimeter; uncertainty parameter reference = 0.01 meter.",
            "prefix": "antity is uncertainty parameter = 0.01 meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 1,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "uncertainty_parameter_reference",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "uncertainty_parameter",
            "value": 0.01,
            "unit": "meter"
          },
          {
            "quantity_kind": "uncertainty_parameter",
            "value": 1,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1843,
            "end": 2088,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand”. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "arameter reference = 0.01 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that m"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [
              "ambiguity:common:005"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1843,
            "end": 2088,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand”. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "arameter reference = 0.01 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that m"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [
              "ambiguity:common:005"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:005",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:005:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:paraphrase",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2103,
            "end": 2326,
            "exact": "In equivalent wording, the document states that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": "d quantity is uncertainty parameter = 0.01 meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA signed measurement error is not the n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_measurement_uncertainty"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      },
      {
        "case_id": "sci-case:common:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:005",
        "claim_packet": {
          "claim_id": "claim:common:005:false_red_prevention",
          "document_ref": "qualification-fixture:common:005",
          "document_digest": "sha256:5707b7873402310427dee82206d59ed5914543695a0820f7ed9db9ca45e6b0ef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2351,
            "end": 2506,
            "exact": "A signed measurement error is not the non-negative uncertainty parameter defined by this rule. The reviewed quantity is uncertainty parameter = 0.01 meter.",
            "prefix": " is uncertainty parameter = 0.01 meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-uncertainty",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dispersion-parameter",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "uncertainty_parameter",
                "value": 0.01,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "signed_measurement_error"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:measurement-uncertainty",
              "sci:binding:common:measurement-error"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:uncertainty-error"
        ],
        "matrix_rule_id": "sci-rule:common:005"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-005

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
