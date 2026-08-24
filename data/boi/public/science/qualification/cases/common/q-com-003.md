---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-003 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:003",
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
      "ref": "sci-rule:common:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:003",
    "standard_id": "Q-COM-003",
    "rule_id": "sci-rule:common:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:003:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:clear_violation",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:e750aef66e9e3e517158b928cd0afa1b66729189362003bacd3d383b11bc41a6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 140,
            "exact": "A one-degree Celsius temperature interval has a different magnitude from a one-kelvin interval. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:in_scope_consistency",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:4e52a3475f80e7b7c5da8a76796a6706caf90ea3fa12981a92d7d5a7327f1c70",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 142,
            "exact": "A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:missing_required_condition",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:47327f2ce211476e96a5c86c5d205c24b5d0282ae2787578d434371b7830ec81",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 201,
            "exact": "Without specifying comparison kind, the report states that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:outside_validity_domain",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:6507eebcb4dbc64a8382b8dec412a807a428c740ef251f51574af0d1f189432d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 213,
            "exact": "In a different scientific context, the report nevertheless states that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:empirical_verification_required",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:daab1a6d91571d93662d4d6447d7d8ec27eb3a7830fc4bb3a30668c32cb6460c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 226,
            "exact": "For a named realization, the report asserts that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              },
              {
                "condition_id": "requested_foundation_003_qualified_observation",
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
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:negation",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:9d49510da4d23c106ab04ed26ebe7bf4284d5cc6e045f05a506ac8da5d1dd258",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 162,
            "exact": "It is not true that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:unit_variation",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:40127f50680d19363a435bc0d9b050ec76ef20ebe4c19ae18c8be0acc13c9bc5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The same temperature interval is written as 1 °C and 1 kelvin.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "°C"
              },
              {
                "quantity_kind": "temperature_interval_reference",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "temperature_interval",
            "value": 1,
            "unit": "kelvin"
          },
          {
            "quantity_kind": "temperature_interval",
            "value": 1,
            "unit": "°C"
          }
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:decision_changing_ambiguity",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:a4ba2a2599e78ab685b936a23ad50faa9a4daef8a597dd6bf55fe611d22476ea",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 292,
            "exact": "The wording leaves unresolved whether 'A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin.' or instead 'A one-degree Celsius temperature interval has a different magnitude from a one-kelvin interval.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [
              "ambiguity:common:003"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:a4ba2a2599e78ab685b936a23ad50faa9a4daef8a597dd6bf55fe611d22476ea",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 292,
            "exact": "The wording leaves unresolved whether 'A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin.' or instead 'A one-degree Celsius temperature interval has a different magnitude from a one-kelvin interval.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [
              "ambiguity:common:003"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:003",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:003:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:paraphrase",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:ca7012c74ee6958355f66c7c820ab4e97108c722f709b68fdb303a795ed85f93",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "In equivalent wording, the document states that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "unit_interval_magnitude"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      },
      {
        "case_id": "sci-case:common:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:003",
        "claim_packet": {
          "claim_id": "claim:common:003:false_red_prevention",
          "document_ref": "qualification:common:003",
          "document_digest": "sha256:950365ee66fbf4489434eeed03e418de0e125176f837650a48ff81f95583a63c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 151,
            "exact": "An absolute Celsius temperature offset is not the unit-interval magnitude comparison covered by this rule. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:celsius-temperature-interval",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:kelvin-temperature-interval",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "temperature_interval",
                "value": 1,
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "comparison_kind",
                "value": "absolute_temperature_offset"
              },
              {
                "condition_id": "unit_pair",
                "value": "degree_celsius_kelvin"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:unit"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:celsius-kelvin"
        ],
        "matrix_rule_id": "sci-rule:common:003"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-003

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
