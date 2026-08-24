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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:39b58c56bca6fc60712d0209e0f4ea1234631963b8172075e5f14b6b827733ba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 149,
            "exact": "Measurement uncertainty is not a non-negative dispersion parameter for values attributed to a measurand. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:c2249d44fca62975fa656a56eca43c8f37b6828f16eebfbdc7fc15507da5f7c9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 159,
            "exact": "Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:8cee84bb317b010ea8dc168ac6a3ec5a18cc0edafb42a28844075c0e8993f5b1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 217,
            "exact": "Without specifying parameter sign, the report states that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:b96c6e2eb206b20c4fa5ef277f832e5dd9734cfd96b66c8f1b6061d68307628a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 230,
            "exact": "In a different scientific context, the report nevertheless states that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:26e3e18ad299664c98a25c7b0b431966014b33471f349b66dc7c1e6e4a6ca634",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 243,
            "exact": "For a named realization, the report asserts that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:076721ae95098972e584a21da4a1922f78518884a864416fb19fb7c6d861c1c8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 179,
            "exact": "It is not true that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:53e5d3d910f87570336c0672b8603d759c1b60535d0b53bf7df6caea84ddc36c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The same uncertainty parameter is written as 1 centimeter and 0.01 meter.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:e1ee3c04833badda6c14232614d0df5c079156a6fbc9c2df836aeb34f811c752",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 318,
            "exact": "The wording leaves unresolved whether 'Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand.' or instead 'Measurement uncertainty is not a non-negative dispersion parameter for values attributed to a measurand.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:e1ee3c04833badda6c14232614d0df5c079156a6fbc9c2df836aeb34f811c752",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 318,
            "exact": "The wording leaves unresolved whether 'Measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand.' or instead 'Measurement uncertainty is not a non-negative dispersion parameter for values attributed to a measurand.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:9ee93b89f23f268b65679ea5ce49fd20bc04ebcc7267091c261d738c9d47e32c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 207,
            "exact": "In equivalent wording, the document states that measurement uncertainty is a non-negative parameter characterizing dispersion of values attributed to a measurand. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "non_negative"
              },
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
          "document_ref": "qualification:common:005",
          "document_digest": "sha256:b44f8aabac31c6db71a7c5b365a6acea8646ddd1885bd61289d05230134eac33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 139,
            "exact": "A signed measurement error is not the non-negative uncertainty parameter defined by this rule. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "parameter_sign",
                "value": "signed_error"
              },
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
        "expected_verdict": "INSUFFICIENT_INFORMATION",
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
