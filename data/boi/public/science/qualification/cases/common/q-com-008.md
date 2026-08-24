---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-008 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:008",
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
      "ref": "sci-rule:common:008"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:008",
    "standard_id": "Q-COM-008",
    "rule_id": "sci-rule:common:008",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:008:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:clear_violation",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 322,
            "exact": "A record of the validation domain of validated modelling and simulation need not be maintained. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA record of the validation domain of va"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "need_not_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:in_scope_consistency",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 347,
            "end": 506,
            "exact": "A record of the validation domain of validated modelling and simulation shall be maintained. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "lidation domain length limit = 1 meter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nA record of the validation domain"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:missing_required_condition",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 537,
            "end": 675,
            "exact": "A record of the validation domain of validated modelling and simulation shall be maintained. No reviewed scale is stated for this fixture.",
            "prefix": "on domain length limit = 1 meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nA record of the validation domain of"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:outside_validity_domain",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 703,
            "end": 943,
            "exact": "A record of the validation domain of validated modelling and simulation shall be maintained. The accompanying scale is a time duration, not the reviewed physical dimension. The reviewed quantity is validation domain length limit = 1 second.",
            "prefix": "ed scale is stated for this fixture.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nA record of the validation d"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:empirical_verification_required",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 979,
            "end": 1209,
            "exact": "A record of the validation domain of validated modelling and simulation shall be maintained. A new unqualified observation requests confirmation of this statement. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "ain length limit = 1 second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a record of the validation doma"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "requested_foundation_008_qualified_observation",
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:negation",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1222,
            "end": 1401,
            "exact": "It is not true that a record of the validation domain of validated modelling and simulation shall be maintained. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "antity is validation domain length limit = 1 meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA record of the validation domain of validate"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:unit_variation",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1420,
            "end": 1641,
            "exact": "A record of the validation domain of validated modelling and simulation shall be maintained. The reviewed quantities are validation domain length limit = 100 centimeter; validation domain length limit reference = 1 meter.",
            "prefix": " is validation domain length limit = 1 meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "validation_domain_length_limit_reference",
                "value": 1,
                "unit": "meter"
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
            "quantity_kind": "validation_domain_length_limit",
            "value": 1,
            "unit": "meter"
          },
          {
            "quantity_kind": "validation_domain_length_limit",
            "value": 100,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1673,
            "end": 1902,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A record of the validation domain of validated modelling and simulation shall be maintained”. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "ength limit reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a record of the validation"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
              "ambiguity:common:008"
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
          "claim_id": "claim:common:008:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1673,
            "end": 1902,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A record of the validation domain of validated modelling and simulation shall be maintained”. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "ength limit reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a record of the validation"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "need_not_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
              "ambiguity:common:008"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:008",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:008:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:paraphrase",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1917,
            "end": 2099,
            "exact": "In equivalent wording, a record of the validation domain of validated modelling and simulation shall be maintained. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "tity is validation domain length limit = 1 meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nThe project archive note says the valid"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "shall_be_maintained",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:false_red_prevention",
          "document_ref": "qualification-fixture:common:008",
          "document_digest": "sha256:60203fa1dfd6d79a69847db3a6203ebc741ad298388f7132c019ab0d2767bff3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2124,
            "end": 2282,
            "exact": "The project archive note says the validation-domain record is archived after project close. The reviewed quantity is validation domain length limit = 1 meter.",
            "prefix": "lidation domain length limit = 1 meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "is_archived_after_project_close",
            "object_concept_id": "sci:concept:record-maintenance",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
        "matrix_rule_id": "sci-rule:common:008"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-008

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
