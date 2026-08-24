---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:002",
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
      "ref": "sci-rule:spin-coating:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:002",
    "standard_id": "Q-SPN-002",
    "rule_id": "sci-rule:spin-coating:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:clear_violation",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:9f64e068b3803703f6f633842686504da75d833f9014cfdf42bbbbba2b4fbca2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 153,
            "exact": "A validation-domain record need not be maintained for a validated model or simulation. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:in_scope_consistency",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:226c680c87fcdc4b3fce4e83ead2c606019cf1f497592f7e9f3fd8aff024fac1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 161,
            "exact": "A record of the domain of validation of the validated model or simulation shall be maintained. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:missing_required_condition",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:d4cad244121099319226567351bca691c4636f6b79a3d0d5ddc4bc4c4d3268e7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 173,
            "exact": "The report states that a validation-domain record shall be maintained, but it does not identify the model. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:outside_validity_domain",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:d8d7225b7578012a9ad7de22120745ff89a10bd6a403a8500f28eecf85a8db68",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 161,
            "exact": "A record used for configuration management is asserted to be a model-validation-domain record. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "configuration_management"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:empirical_verification_required",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:44e0f1dd92ef8183ce8e8b5bdb0f9f777da0b203d300173baf2cb6f78cb5a2f7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 192,
            "exact": "The report claims that a named model has a maintained validation-domain record, but no qualified record observation is bound. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              },
              {
                "condition_id": "requested_model_validation_record_observation",
                "value": "unqualified_observation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:negation",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:04aa0817fac0b17b3445cdddbd0e15387ffdf5a9850b501337996048d6defed8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 164,
            "exact": "It is not true that a validation-domain record shall be maintained for the named validated model. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:unit_variation",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:539f7af255f817cb2765059c438727bc1fc17091f414d1a5532c69a17d42996a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 233,
            "exact": "A record of the domain of validation of the validated model or simulation shall be maintained. The validation domain temperature limit is recorded as 26.85 °C. The same validation domain temperature limit is referenced as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
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
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:decision_changing_ambiguity",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:47abbca49b88127c818303aec2b694d5a27e359921ca57016ad84b33bea5d714",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "The wording leaves unresolved whether a validation-domain record is or is not required for the named validated model. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:47abbca49b88127c818303aec2b694d5a27e359921ca57016ad84b33bea5d714",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "The wording leaves unresolved whether a validation-domain record is or is not required for the named validated model. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:paraphrase",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:344dd6164faae68b737263f038a85a9995bb9655822984f3e4202cea6e6784e7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 141,
            "exact": "The validated model must retain a record describing its validation domain. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "same_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:false_red_prevention",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:1256ca731a934eac5a6a4b84b08fadf63f04ce55df07d425b4e50b8636322682",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 179,
            "exact": "A validation-domain record maintained for a different model does not satisfy the named model record requirement. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model-validation-domain-record",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:record-maintenance",
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
                "condition_id": "model_identity",
                "value": "named_model"
              },
              {
                "condition_id": "validation_record_scope",
                "value": "different_model"
              },
              {
                "condition_id": "record_maintenance_context",
                "value": "model_validation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SPN-002

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:002`. No operational authority is created.
