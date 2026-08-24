---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-010 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:010",
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
      "ref": "sci-rule:common:010"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:010",
    "standard_id": "Q-COM-010",
    "rule_id": "sci-rule:common:010",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:010:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:clear_violation",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:39db1661da49ef781757e525a5ef651f12e67966e961bddd8ab060f7b06d386c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 136,
            "exact": "Steady state and dynamic equilibrium are identical scientific definitions in every respect. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "identical_to",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:in_scope_consistency",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:af34d7ce3cc77b07db5eb0e73dce875ff675d11af49345071ba685b3ee5456b6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 183,
            "exact": "Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:missing_required_condition",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:609565142631dc4d4ac8f80e3844f51fcd478717f7e48ce690c08ac2f19614ae",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 254,
            "exact": "Without specifying steady state temporal basis, the report states that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:outside_validity_domain",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:2fc7546affece8c0b015fb2c26c0d08350f4b3b7ceb11fa81f8093fb60cf792f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 254,
            "exact": "In a different scientific context, the report nevertheless states that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:empirical_verification_required",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:1d748070ae7a56b70e5f7eac98c28b7529f6d0b212dab9021f8d5dfe51474404",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 267,
            "exact": "For a named realization, the report asserts that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              },
              {
                "condition_id": "requested_foundation_010_qualified_observation",
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
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:negation",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:ce392af327a6d8f5211b7a9387c1b803e5a9c35915004e878a385cbf6f72fbb6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 203,
            "exact": "It is not true that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:unit_variation",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:a7ff1cf3dd86c66af5eea627c439f12a0f50f4e536be4ccf9e6ef25be67fff8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 213,
            "exact": "Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The same observation duration is written as 1000 millisecond and 1 second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1000,
                "unit": "millisecond"
              },
              {
                "quantity_kind": "observation_duration_reference",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "observation_duration",
            "value": 1,
            "unit": "second"
          },
          {
            "quantity_kind": "observation_duration",
            "value": 1000,
            "unit": "millisecond"
          }
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:decision_changing_ambiguity",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:679f29f2d5b9381661987aa04579920a06754ad4d7e6995091d5418691f39607",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 329,
            "exact": "The wording leaves unresolved whether 'Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change.' or instead 'Steady state and dynamic equilibrium are identical scientific definitions in every respect.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [
              "ambiguity:common:010"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:010:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:679f29f2d5b9381661987aa04579920a06754ad4d7e6995091d5418691f39607",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 329,
            "exact": "The wording leaves unresolved whether 'Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change.' or instead 'Steady state and dynamic equilibrium are identical scientific definitions in every respect.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "identical_to",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [
              "ambiguity:common:010"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:010",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:010:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:paraphrase",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:9dbc81fc5d51b4f86a9eb1cbb214f6acac76b206e90c8f8d131a9c21564f1c8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 231,
            "exact": "In equivalent wording, the document states that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "distinct_from",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "time_independent"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      },
      {
        "case_id": "sci-case:common:010:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:010",
        "claim_packet": {
          "claim_id": "claim:common:010:false_red_prevention",
          "document_ref": "qualification:common:010",
          "document_digest": "sha256:d23ad8e8af8abadbfcbbe78574c7d83261fc924d48fe7cfecf2dbf72ee973a31",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 144,
            "exact": "A transient observation is not a time-independent steady state in this definitions-only comparison. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:steady-state",
            "relation_kind": "empirical_relation",
            "predicate": "identical_to",
            "object_concept_id": "sci:concept:equilibrium",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "observation_duration",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "steady_state_temporal_basis",
                "value": "transient"
              },
              {
                "condition_id": "equilibrium_kinetic_basis",
                "value": "equal_forward_reverse_rates"
              },
              {
                "condition_id": "comparison_scope",
                "value": "definitions_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:steady-state",
              "sci:binding:common:equilibrium"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:steady-state",
          "sci-evidence:common:equilibrium"
        ],
        "matrix_rule_id": "sci-rule:common:010"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-010

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
