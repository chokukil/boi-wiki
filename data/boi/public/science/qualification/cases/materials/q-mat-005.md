---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-MAT-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:materials:005",
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
      "ref": "sci-rule:materials:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:materials:005",
    "standard_id": "Q-MAT-005",
    "rule_id": "sci-rule:materials:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:materials:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:clear_violation",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 337,
            "exact": "For the same chemical composition, a bulk mechanical property is automatically equal to the deposited thin-film property. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nEven at the same chemical composition, "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "automatically_equal",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:in_scope_consistency",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 362,
            "end": 576,
            "exact": "Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the property c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:missing_required_condition",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 607,
            "end": 880,
            "exact": "Without specifying the property class, the report asserts: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "scale is recorded as 1 nanometer.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a nonmechanical property not cov"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:outside_validity_domain",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 908,
            "end": 1201,
            "exact": "For a nonmechanical property not covered by this evidence, the report asserts: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ss scale is recorded as 1 nanometer.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named deposited film a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "outside_deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:empirical_verification_required",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1237,
            "end": 1555,
            "exact": "For a named deposited film and bulk coupon, the report asserts: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. This named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": " is recorded as 1 nanometer.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "requested_thin_film_property_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:negation",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1568,
            "end": 1842,
            "exact": "Under the stated scientific conditions, it is not true that even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "he film thickness scale is recorded as 1 nanometer.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nEven at the same chemical composition, a thin"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:unit_variation",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1861,
            "end": 2137,
            "exact": "Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The reviewed quantities are film thickness scale = 0.001 micrometer; film thickness scale reference = 1 nanometer.",
            "prefix": "m thickness scale is recorded as 1 nanometer.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": "0.001",
                "unit": "micrometer"
              },
              {
                "quantity_kind": "film_thickness_scale_reference",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "film_thickness_scale",
            "value": 1,
            "unit": "nanometer"
          },
          {
            "quantity_kind": "film_thickness_scale",
            "value": "0.001",
            "unit": "micrometer"
          }
        ]
      },
      {
        "case_id": "sci-case:materials:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2169,
            "end": 2461,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Even "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:materials:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:materials:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2169,
            "end": 2461,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Even "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "automatically_equal",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:materials:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:materials:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:paraphrase",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2476,
            "end": 2734,
            "exact": "In equivalent wording, the document states: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "d quantity is film thickness scale = 1 nanometer.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA bulk specimen and deposited thin film"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:false_red_prevention",
          "document_ref": "qualification-fixture:materials:005",
          "document_digest": "sha256:cbe82152a66d65ba5499cbd7dd8bcb997703846fba93b3a87b4e03e6020bea32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2759,
            "end": 2926,
            "exact": "A bulk specimen and deposited thin film of different composition are reported to have equal mechanical properties. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "automatically_equal",
            "object_concept_id": "sci:concept:thin-film-property",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "different"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-MAT-005

Ten public natural-claim fixtures qualify only `sci-rule:materials:005`. No operational authority is created.
