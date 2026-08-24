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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 321,
            "exact": "A length term can equal a time term while the equation remains dimensionally homogeneous. The reviewed quantities are left term = 1 meter; right term = 1 second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nIn the reviewed two-term length example"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 346,
            "end": 519,
            "exact": "In the reviewed two-term length example, both sides of the equality have length dimensionality. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": " term = 1 meter; right term = 1 second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying equation form,"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 550,
            "end": 780,
            "exact": "Without specifying equation form, the report states that in the reviewed two-term length example, both sides of the equality have length dimensionality. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": "ter; right term = 100 centimeter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 808,
            "end": 1052,
            "exact": "In a different scientific context, the report nevertheless states that in the reviewed two-term length example, both sides of the equality have length dimensionality. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": " meter; right term = 100 centimeter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1088,
            "end": 1345,
            "exact": "For a named realization, the report asserts that in the reviewed two-term length example, both sides of the equality have length dimensionality. No qualified observation is bound. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": "right term = 100 centimeter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that in the reviewed two-term length"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1358,
            "end": 1551,
            "exact": "It is not true that in the reviewed two-term length example, both sides of the equality have length dimensionality. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": "e left term = 1 meter; right term = 100 centimeter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nIn the reviewed two-term length example, both"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1570,
            "end": 1752,
            "exact": "In the reviewed two-term length example, both sides of the equality have length dimensionality. The reviewed quantities are left term = 100 centimeter; left term reference = 1 meter.",
            "prefix": " term = 1 meter; right term = 100 centimeter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1784,
            "end": 2027,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “In the reviewed two-term length example, both sides of the equality have length dimensionality”. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": "; left term reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that i"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1784,
            "end": 2027,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “In the reviewed two-term length example, both sides of the equality have length dimensionality”. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": "; left term reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that i"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2042,
            "end": 2263,
            "exact": "In equivalent wording, the document states that in the reviewed two-term length example, both sides of the equality have length dimensionality. The reviewed quantities are left term = 1 meter; right term = 100 centimeter.",
            "prefix": "left term = 1 meter; right term = 100 centimeter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA mass-energy relation is not the revie"
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
          "document_ref": "qualification-fixture:common:002",
          "document_digest": "sha256:1f0c8ca9445cedf859fce44ff5376e30430e1e7b84f833123f1225b23719fc49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2288,
            "end": 2437,
            "exact": "A mass-energy relation is not the reviewed equality between two length terms. The reviewed quantities are left term = 1 meter; right term = 1 second.",
            "prefix": "= 1 meter; right term = 100 centimeter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
