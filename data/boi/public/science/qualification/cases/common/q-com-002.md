---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-002 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:002",
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
      "ref": "sci-rule:common:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:002",
    "standard_id": "Q-COM-002",
    "rule_id": "sci-rule:common:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:002:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:clear_violation",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:1baeddffbc0dddf8d39fc0fdeb0e528145ede1e9781364ff6e38328909370a57",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 179,
            "exact": "A length term can equal a time term while the equation remains dimensionally homogeneous. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:in_scope_consistency",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:1f5e7287f1724d214bc8572d80dc15110db3a12a5f77bf611f1dedd5db3ade72",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 185,
            "exact": "In the reviewed two-term length example, both sides of the equality have length dimensionality. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:missing_required_condition",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:d4d57208e40430428c8411d1dde3d55b68e300a64fae47e26ae05c884f08d6b0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 242,
            "exact": "Without specifying equation form, the report states that in the reviewed two-term length example, both sides of the equality have length dimensionality. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:outside_validity_domain",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:bd13e92f2bd66205c9039a2e1f4323411ea54a437a0d164e87414c33f9a92252",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 256,
            "exact": "In a different scientific context, the report nevertheless states that in the reviewed two-term length example, both sides of the equality have length dimensionality. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:empirical_verification_required",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:ee168bf54fcd8cb0189fae329cfb3d3fe40c6699672953a252e4803104257e0a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 269,
            "exact": "For a named realization, the report asserts that in the reviewed two-term length example, both sides of the equality have length dimensionality. No qualified observation is bound. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              },
              {
                "condition_id": "requested_foundation_002_qualified_observation",
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:negation",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:96955fc78fe4ca7bb56506e23621f0045c302687823337c2720190b24e94702e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 205,
            "exact": "It is not true that in the reviewed two-term length example, both sides of the equality have length dimensionality. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:unit_variation",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:3b9b07db1693121e6923d2ba635408f4ba6dbe43b4f5a3056d805b1acd9b92ca",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 156,
            "exact": "In the reviewed two-term length example, both sides of the equality have length dimensionality. The same left term is written as 100 centimeter and 1 meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "left_term",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "left_term_reference",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
            "quantity_kind": "left_term",
            "value": 1,
            "unit": "meter"
          },
          {
            "quantity_kind": "left_term",
            "value": 100,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:decision_changing_ambiguity",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:ab4e0659edf4ee21496da7e43780cb32affe3a9903d69da760b3dd26b45e737f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 329,
            "exact": "The wording leaves unresolved whether 'In the reviewed two-term length example, both sides of the equality have length dimensionality.' or instead 'A length term can equal a time term while the equation remains dimensionally homogeneous.'. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [
              "ambiguity:common:002"
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
          "claim_id": "claim:common:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:ab4e0659edf4ee21496da7e43780cb32affe3a9903d69da760b3dd26b45e737f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 329,
            "exact": "The wording leaves unresolved whether 'In the reviewed two-term length example, both sides of the equality have length dimensionality.' or instead 'A length term can equal a time term while the equation remains dimensionally homogeneous.'. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [
              "ambiguity:common:002"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:002",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:002:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:paraphrase",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:812bb3c5ab4b0fb86c6a60ebd610d0c16902b5cf36249d4a84fbf74b55a31c99",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 233,
            "exact": "In equivalent wording, the document states that in the reviewed two-term length example, both sides of the equality have length dimensionality. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 100,
                "unit": "centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "equality_two_length_terms"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
        "matrix_rule_id": "sci-rule:common:002"
      },
      {
        "case_id": "sci-case:common:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:002",
        "claim_packet": {
          "claim_id": "claim:common:002:false_red_prevention",
          "document_ref": "qualification:common:002",
          "document_digest": "sha256:e41feefb2599006e87f5f1e4b06b8b24a30193c5ebad386a5c5aa07781ea5401",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 167,
            "exact": "A mass-energy relation is not the reviewed equality between two length terms. The quantity kind is recorded as value unit. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:quantity-equation",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dimensional-homogeneity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "left_term",
                "value": 1,
                "unit": "meter"
              },
              {
                "quantity_kind": "right_term",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "equation_form",
                "value": "mass_energy_relation"
              },
              {
                "condition_id": "coverage_scope",
                "value": "registered_length_units"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
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
        "matrix_rule_id": "sci-rule:common:002"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-002

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
