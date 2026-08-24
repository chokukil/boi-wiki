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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:f2de4811b9f802da71b879da79d8de1aa0f6f1928463eda2c62150434efd5e5b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 140,
            "exact": "No validation-domain record needs to be maintained for the named validated model or simulation. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:dcb88e969629ab5d4a3325aad487b1fe4dda539b7cf9b82513962176ab8c46b9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 145,
            "exact": "A record of the domain of validation of the named validated model or simulation shall be maintained. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:d43e1040e9be9bdd8476fb5a4d960ae8522b8c544031b65b5b011dcda7a8c383",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 203,
            "exact": "Without specifying model identity, the report states that a record of the domain of validation of the named validated model or simulation shall be maintained. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:11bce0cd6497f65f9b10ca437c418f43b9cc8730ab6a93775806a958b9dbd172",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 216,
            "exact": "In a different scientific context, the report nevertheless states that a record of the domain of validation of the named validated model or simulation shall be maintained. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
        "matrix_rule_id": "sci-rule:common:008"
      },
      {
        "case_id": "sci-case:common:008:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:008:empirical_verification_required",
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:4af849b349885016daeb7a748b2a739708f3a278a8653141975b685e033c0906",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "For a named realization, the report asserts that a record of the domain of validation of the named validated model or simulation shall be maintained. No qualified observation is bound. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:c19cc3427f38b910b707221808c298297efce883fea8c6452f51672aa6fef0ae",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 165,
            "exact": "It is not true that a record of the domain of validation of the named validated model or simulation shall be maintained. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:7fb51ba56f48d79578767d84c5c8556c54598760230fd0f83ec912ed2eabefbb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 182,
            "exact": "A record of the domain of validation of the named validated model or simulation shall be maintained. The same validation domain length limit is written as 100 centimeter and 1 meter.",
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:1aa34449a40ff714e7d6fe4a4663d63f9e3d1df47080e7eec985c917f76b1521",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 295,
            "exact": "The wording leaves unresolved whether 'A record of the domain of validation of the named validated model or simulation shall be maintained.' or instead 'No validation-domain record needs to be maintained for the named validated model or simulation.'. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:1aa34449a40ff714e7d6fe4a4663d63f9e3d1df47080e7eec985c917f76b1521",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 295,
            "exact": "The wording leaves unresolved whether 'A record of the domain of validation of the named validated model or simulation shall be maintained.' or instead 'No validation-domain record needs to be maintained for the named validated model or simulation.'. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:2a6ef09d524daf3f14203df2cbe63e8a52ef4312be4b5eb5ed420ad0a5017075",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 193,
            "exact": "In equivalent wording, the document states that a record of the domain of validation of the named validated model or simulation shall be maintained. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
          "document_ref": "qualification:common:008",
          "document_digest": "sha256:17ab3d0d5d1ca694fd5e93ea01c1754d126c8407a4f89b9d0e9e07e96527d616",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 146,
            "exact": "A validation-domain record for a different model does not satisfy the named model record requirement. The quantity kind is recorded as value unit.",
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
                "quantity_kind": "validation_domain_length_limit",
                "value": 1,
                "unit": "meter"
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
