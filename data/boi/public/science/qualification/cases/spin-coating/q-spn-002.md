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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 166,
            "end": 319,
            "exact": "A validation-domain record need not be maintained for a validated model or simulation. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA record of the domain of validation of"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 344,
            "end": 505,
            "exact": "A record of the domain of validation of the validated model or simulation shall be maintained. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "rature limit is recorded as 300 kelvin.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report states that a validati"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 536,
            "end": 709,
            "exact": "The report states that a validation-domain record shall be maintained, but it does not identify the model. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": " limit is recorded as 300 kelvin.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nA record used for configuration mana"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 737,
            "end": 898,
            "exact": "A record used for configuration management is asserted to be a model-validation-domain record. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "ure limit is recorded as 300 kelvin.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nThe report claims that a nam"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 934,
            "end": 1126,
            "exact": "The report claims that a named model has a maintained validation-domain record, but no qualified record observation is bound. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "t is recorded as 300 kelvin.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a validation-domain record shal"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1139,
            "end": 1303,
            "exact": "It is not true that a validation-domain record shall be maintained for the named validated model. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "domain temperature limit is recorded as 300 kelvin.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA record of the domain of validation of the v"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1322,
            "end": 1552,
            "exact": "A record of the domain of validation of the validated model or simulation shall be maintained. The reviewed quantities are validation domain temperature limit = 26.85 °C; validation domain temperature limit reference = 300 kelvin.",
            "prefix": " temperature limit is recorded as 300 kelvin.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1584,
            "end": 1823,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A record of the domain of validation of the validated model or simulation shall be maintained”. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "re limit reference = 300 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nThe validated model must retain a record describi"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1584,
            "end": 1823,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A record of the domain of validation of the validated model or simulation shall be maintained”. The reviewed quantity is validation domain temperature limit = 300 kelvin.",
            "prefix": "re limit reference = 300 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nThe validated model must retain a record describi"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1838,
            "end": 1979,
            "exact": "The validated model must retain a record describing its validation domain. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "validation domain temperature limit = 300 kelvin.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA validation-domain record maintained f"
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
          "document_ref": "qualification-fixture:spin-coating:002",
          "document_digest": "sha256:6be799276553aeb052cffb74db6318d9c89f01866830d0c2535705172e834e47",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2004,
            "end": 2183,
            "exact": "A validation-domain record maintained for a different model does not satisfy the named model record requirement. The validation domain temperature limit is recorded as 300 kelvin.",
            "prefix": "rature limit is recorded as 300 kelvin.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
