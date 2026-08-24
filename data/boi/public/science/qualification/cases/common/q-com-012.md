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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:69e40e7757225a6c7b56250deb98e80ec9d770b7aa39adcccd98cd0b26624880",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 121,
            "exact": "An observed correlation by itself proves that one variable causes the other. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:2dafe7b3af66fa180e15914ff562324441df7023bacc619abd6465ca69aace62",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 119,
            "exact": "An observed correlation does not imply that one variable causes the other. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:4b2d27df327f9105b88ae12f47ffd687f9684e2a68cc01de8fa7392c7bbd2c89",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 186,
            "exact": "Without specifying observed relation basis, the report states that an observed correlation does not imply that one variable causes the other. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:3db5d45dbb69d71d8566185c07b5cd8688029cd5b90c1fa63c8f382e48145f2c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "In a different scientific context, the report nevertheless states that an observed correlation does not imply that one variable causes the other. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:4ea9852c5f198729417594d7a5cf78e5c4c74919d95da1bd5418cbff2901334b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 203,
            "exact": "For a named realization, the report asserts that an observed correlation does not imply that one variable causes the other. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:89d58b7fbcb3e0c4da2f551e9cb5da132cbfbd042b341239cdd87686defe3ec4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 139,
            "exact": "It is not true that an observed correlation does not imply that one variable causes the other. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:c022c77dd232f8334a77b56dfc51f93894e7ca71bcfac595082a3b1a5beecc06",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 155,
            "exact": "An observed correlation does not imply that one variable causes the other. The same correlation coefficient is written as 50 percent and 0.5 dimensionless.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:faf728d6a8c0076d0e43ed65657dadc78f4d76080e65ac6de96e272d33b85caf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 250,
            "exact": "The wording leaves unresolved whether 'An observed correlation does not imply that one variable causes the other.' or instead 'An observed correlation by itself proves that one variable causes the other.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:faf728d6a8c0076d0e43ed65657dadc78f4d76080e65ac6de96e272d33b85caf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 250,
            "exact": "The wording leaves unresolved whether 'An observed correlation does not imply that one variable causes the other.' or instead 'An observed correlation by itself proves that one variable causes the other.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:a3a28e797da649bd8f68e860e1376d2914f6a1ae8b18b9df345875ffb33a23f0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 167,
            "exact": "In equivalent wording, the document states that an observed correlation does not imply that one variable causes the other. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:012",
          "document_digest": "sha256:06d893984467a9b046c449e5bcfdd6d9a9b3449a22dee52f2637df5ef1737425",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 162,
            "exact": "A broad association without a quantified correlation is not silently treated as the correlation premise of this rule. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
