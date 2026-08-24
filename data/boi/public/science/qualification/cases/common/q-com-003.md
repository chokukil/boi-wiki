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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 313,
            "exact": "A one-degree Celsius temperature interval has a different magnitude from a one-kelvin interval. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA temperature interval of one degree Ce"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 338,
            "end": 493,
            "exact": "A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "ity is temperature interval = 1 kelvin.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying comparison kin"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 524,
            "end": 738,
            "exact": "Without specifying comparison kind, the report states that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": " temperature interval = 1 kelvin.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 766,
            "end": 992,
            "exact": "In a different scientific context, the report nevertheless states that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": " is temperature interval = 1 kelvin.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1028,
            "end": 1267,
            "exact": "For a named realization, the report asserts that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. No qualified observation is bound. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "erature interval = 1 kelvin.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a temperature interval of one d"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1280,
            "end": 1455,
            "exact": "It is not true that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "viewed quantity is temperature interval = 1 kelvin.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA temperature interval of one degree Celsius "
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1474,
            "end": 1671,
            "exact": "A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The reviewed quantities are temperature interval = 1 °C; temperature interval reference = 1 kelvin.",
            "prefix": " quantity is temperature interval = 1 kelvin.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1703,
            "end": 1928,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin”. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "e interval reference = 1 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1703,
            "end": 1928,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin”. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "e interval reference = 1 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1943,
            "end": 2146,
            "exact": "In equivalent wording, the document states that a temperature interval of one degree Celsius has the same magnitude as an interval of one kelvin. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "ewed quantity is temperature interval = 1 kelvin.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAn absolute Celsius temperature offset "
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
          "document_ref": "qualification-fixture:common:003",
          "document_digest": "sha256:47b4f702a54c64b49e7a40a434baa2e6f5587d79dc8c539df8985f2a444e3d9e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2171,
            "end": 2335,
            "exact": "An absolute Celsius temperature offset is not the unit-interval magnitude comparison covered by this rule. The reviewed quantity is temperature interval = 1 kelvin.",
            "prefix": "ity is temperature interval = 1 kelvin.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
