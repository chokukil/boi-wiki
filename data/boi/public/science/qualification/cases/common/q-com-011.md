---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-011 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:011",
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
      "ref": "sci-rule:common:011"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:011",
    "standard_id": "Q-COM-011",
    "rule_id": "sci-rule:common:011",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:011:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:clear_violation",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 309,
            "exact": "A model-validation-domain record need not record any domain of validation. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA model-validation-domain record record"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "need_not_record_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:in_scope_consistency",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 334,
            "end": 516,
            "exact": "A model-validation-domain record records the domain of validation of the validated modelling or simulation. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": " domain temperature limit = 300 kelvin.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nA model-validation-domain record "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:missing_required_condition",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 547,
            "end": 700,
            "exact": "A model-validation-domain record records the domain of validation of the validated modelling or simulation. No reviewed scale is stated for this fixture.",
            "prefix": "n temperature limit = 300 kelvin.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nA model-validation-domain record rec"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [],
            "conditions": [],
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
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:outside_validity_domain",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 728,
            "end": 990,
            "exact": "A model-validation-domain record records the domain of validation of the validated modelling or simulation. The accompanying scale is a time duration, not the reviewed physical dimension. The reviewed quantity is validation domain temperature limit = 300 second.",
            "prefix": "ed scale is stated for this fixture.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nA model-validation-domain re"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "second"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:empirical_verification_required",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1026,
            "end": 1279,
            "exact": "A model-validation-domain record records the domain of validation of the validated modelling or simulation. A new unqualified observation requests confirmation of this statement. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "perature limit = 300 second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a model-validation-domain recor"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "requested_foundation_011_qualified_observation",
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
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:negation",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1292,
            "end": 1494,
            "exact": "It is not true that a model-validation-domain record records the domain of validation of the validated modelling or simulation. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "s validation domain temperature limit = 300 kelvin.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA model-validation-domain record records the "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:unit_variation",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1513,
            "end": 1756,
            "exact": "A model-validation-domain record records the domain of validation of the validated modelling or simulation. The reviewed quantities are validation domain temperature limit = 26.85 °C; validation domain temperature limit reference = 300 kelvin.",
            "prefix": "dation domain temperature limit = 300 kelvin.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 26.85,
                "unit": "°C"
              },
              {
                "quantity_kind": "validation_domain_temperature_limit_reference",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "validation_domain_temperature_limit",
            "value": 300,
            "unit": "kelvin"
          },
          {
            "quantity_kind": "validation_domain_temperature_limit",
            "value": 26.85,
            "unit": "°C"
          }
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1788,
            "end": 2040,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A model-validation-domain record records the domain of validation of the validated modelling or simulation”. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "re limit reference = 300 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a model-validation-domain "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:model"
            ],
            "ambiguity_ids": [
              "ambiguity:common:011"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:011:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1788,
            "end": 2040,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A model-validation-domain record records the domain of validation of the validated modelling or simulation”. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "re limit reference = 300 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a model-validation-domain "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "need_not_record_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:model"
            ],
            "ambiguity_ids": [
              "ambiguity:common:011"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:011",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:011:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:paraphrase",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2055,
            "end": 2260,
            "exact": "In equivalent wording, a model-validation-domain record records the domain of validation of the validated modelling or simulation. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "validation domain temperature limit = 300 kelvin.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nThe configuration-history record lists "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_validation_domain",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      },
      {
        "case_id": "sci-case:common:011:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:011",
        "claim_packet": {
          "claim_id": "claim:common:011:false_red_prevention",
          "document_ref": "qualification-fixture:common:011",
          "document_digest": "sha256:377c65478a3532b7ff24b82f9a72924efc6a9d9fefea139f8b1af6177c77eb26",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2285,
            "end": 2455,
            "exact": "The configuration-history record lists software revisions but makes no validation-domain claim. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": " domain temperature limit = 300 kelvin.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "records_configuration_history",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [],
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
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "matrix_rule_id": "sci-rule:common:011"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-011

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
