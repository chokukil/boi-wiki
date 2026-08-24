---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-012 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:012",
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
      "ref": "sci-rule:common:012"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:012",
    "standard_id": "Q-COM-012",
    "rule_id": "sci-rule:common:012",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:012:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:clear_violation",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 306,
            "exact": "An observed correlation by itself proves that one variable causes the other. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nAn observed correlation does not imply "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "implies",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:in_scope_consistency",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 331,
            "end": 475,
            "exact": "An observed correlation does not imply that one variable causes the other. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "lation coefficient = 0.5 dimensionless.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying observed relat"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:missing_required_condition",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 506,
            "end": 717,
            "exact": "Without specifying observed relation basis, the report states that an observed correlation does not imply that one variable causes the other. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": " coefficient = 0.5 dimensionless.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:outside_validity_domain",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 745,
            "end": 960,
            "exact": "In a different scientific context, the report nevertheless states that an observed correlation does not imply that one variable causes the other. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "ion coefficient = 0.5 dimensionless.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:empirical_verification_required",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 996,
            "end": 1224,
            "exact": "For a named realization, the report asserts that an observed correlation does not imply that one variable causes the other. No qualified observation is bound. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "ficient = 0.5 dimensionless.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that an observed correlation does no"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "requested_foundation_012_qualified_observation",
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
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:negation",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1237,
            "end": 1401,
            "exact": "It is not true that an observed correlation does not imply that one variable causes the other. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "ity is correlation coefficient = 0.5 dimensionless.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nAn observed correlation does not imply that o"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:unit_variation",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1420,
            "end": 1615,
            "exact": "An observed correlation does not imply that one variable causes the other. The reviewed quantities are correlation coefficient = 50 percent; correlation coefficient reference = 0.5 dimensionless.",
            "prefix": " correlation coefficient = 0.5 dimensionless.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 50,
                "unit": "percent"
              },
              {
                "quantity_kind": "correlation_coefficient_reference",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "correlation_coefficient",
            "value": 0.5,
            "unit": "dimensionless"
          },
          {
            "quantity_kind": "correlation_coefficient",
            "value": 50,
            "unit": "percent"
          }
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1647,
            "end": 1861,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “An observed correlation does not imply that one variable causes the other”. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "t reference = 0.5 dimensionless.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [
              "ambiguity:common:012"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:012:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1647,
            "end": 1861,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “An observed correlation does not imply that one variable causes the other”. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "t reference = 0.5 dimensionless.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "implies",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [
              "ambiguity:common:012"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:012",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:012:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:paraphrase",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1876,
            "end": 2068,
            "exact": "In equivalent wording, the document states that an observed correlation does not imply that one variable causes the other. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "y is correlation coefficient = 0.5 dimensionless.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA broad association without a quantifie"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "does_not_imply",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "correlation_only"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      },
      {
        "case_id": "sci-case:common:012:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:012",
        "claim_packet": {
          "claim_id": "claim:common:012:false_red_prevention",
          "document_ref": "qualification-fixture:common:012",
          "document_digest": "sha256:c119e4122a60bcb58cae5daf003479d77cc21c3c099f4697f380bb2fcad81f45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2093,
            "end": 2280,
            "exact": "A broad association without a quantified correlation is not silently treated as the correlation premise of this rule. The reviewed quantity is correlation coefficient = 0.5 dimensionless.",
            "prefix": "lation coefficient = 0.5 dimensionless.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:correlation",
            "relation_kind": "causal_relation",
            "predicate": "implies",
            "object_concept_id": "sci:concept:causation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "correlation_coefficient",
                "value": 0.5,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "observed_relation_basis",
                "value": "association_without_quantified_correlation"
              },
              {
                "condition_id": "causal_evidence_basis",
                "value": "correlation_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:correlation",
              "sci:binding:common:causation"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:correlation-causation"
        ],
        "matrix_rule_id": "sci-rule:common:012"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-012

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
