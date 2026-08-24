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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:1c34fe66fcf5f01c78d6335c1ec1a3270aad8a1964af7a0cd72be8e56cef6519",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 118,
            "exact": "A model-validation-domain record need not identify any validation domain. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:2b2c6640013f66ff56b989c1b029c7caff1595747d800bf762516c330e137f8f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 152,
            "exact": "The bound model-validation record identifies the domain of validation of the validated model or simulation. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:194df5530f647515050f336b4f934e43268c52ea861eec2e2c02019a8a426a06",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 211,
            "exact": "Without specifying record identity, the report states that the bound model-validation record identifies the domain of validation of the validated model or simulation. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
                "condition_id": "record_content",
                "value": "validation_domain"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:234be0b9b7050f528930b41d03d3dfdf48a2c54b0ddd55acae0cdb5b8bb9b46d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 223,
            "exact": "In a different scientific context, the report nevertheless states that the bound model-validation record identifies the domain of validation of the validated model or simulation. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "different_scientific_context"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:f8e6f26972bd207e674feefac7cc360e04c1a54dcaa5205a0776b2fdecbd7df3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 236,
            "exact": "For a named realization, the report asserts that the bound model-validation record identifies the domain of validation of the validated model or simulation. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
              },
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:8ca7f4f1ba0fc4128a93872aee685233715788afc43c143165596f3004beca06",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 172,
            "exact": "It is not true that the bound model-validation record identifies the domain of validation of the validated model or simulation. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:da3bcd77e589784852dc39ad6c8a8151c3c3d563df50116334f79a1879b9be96",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 191,
            "exact": "The bound model-validation record identifies the domain of validation of the validated model or simulation. The same validation domain temperature limit is written as 26.85 °C and 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
            "conditions": [
              {
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:11c5cf88c3a959a6db243c7be0c0fe5374e88bc23aade8fb29390ffcf5863f29",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 280,
            "exact": "The wording leaves unresolved whether 'The bound model-validation record identifies the domain of validation of the validated model or simulation.' or instead 'A model-validation-domain record need not identify any validation domain.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
              }
            ],
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:11c5cf88c3a959a6db243c7be0c0fe5374e88bc23aade8fb29390ffcf5863f29",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 280,
            "exact": "The wording leaves unresolved whether 'The bound model-validation record identifies the domain of validation of the validated model or simulation.' or instead 'A model-validation-domain record need not identify any validation domain.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
              }
            ],
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:64c9b7eec4c4241b997e51a63299df745ef4b7ce3fed9a99b714c2ede48bcd80",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 200,
            "exact": "In equivalent wording, the document states that the bound model-validation record identifies the domain of validation of the validated model or simulation. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
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
                "condition_id": "record_identity",
                "value": "bound_validation_record"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
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
          "document_ref": "qualification:common:011",
          "document_digest": "sha256:a52d8cb2a6874f4ac1d59c4d2c12a67f44c4c909d3711bc74ec6e309b0a9f7cd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 136,
            "exact": "A configuration log is not the bound model-validation-domain record addressed by this rule. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:validation-domain",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "validation_domain_temperature_limit",
                "value": 300,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "record_identity",
                "value": "configuration_log"
              },
              {
                "condition_id": "record_content",
                "value": "validation_domain"
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
