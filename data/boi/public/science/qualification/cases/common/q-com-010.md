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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 309,
            "exact": "Steady state and dynamic equilibrium are identical scientific definitions in every respect. The reviewed quantity is observation duration = 1 second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nSteady state is time independent, where"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 334,
            "end": 530,
            "exact": "Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The reviewed quantity is observation duration = 1 second.",
            "prefix": "ity is observation duration = 1 second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying steady state t"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 561,
            "end": 828,
            "exact": "Without specifying steady state temporal basis, the report states that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The reviewed quantity is observation duration = 1 second.",
            "prefix": " observation duration = 1 second.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 856,
            "end": 1123,
            "exact": "In a different scientific context, the report nevertheless states that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The reviewed quantity is observation duration = 1 second.",
            "prefix": " is observation duration = 1 second.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1159,
            "end": 1439,
            "exact": "For a named realization, the report asserts that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. No qualified observation is bound. The reviewed quantity is observation duration = 1 second.",
            "prefix": "rvation duration = 1 second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that steady state is time independen"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1452,
            "end": 1668,
            "exact": "It is not true that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The reviewed quantity is observation duration = 1 second.",
            "prefix": "viewed quantity is observation duration = 1 second.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nSteady state is time independent, whereas dyn"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1687,
            "end": 1937,
            "exact": "Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The reviewed quantities are observation duration = 1000 millisecond; observation duration reference = 1 second.",
            "prefix": " quantity is observation duration = 1 second.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1969,
            "end": 2235,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change”. The reviewed quantity is observation duration = 1 second.",
            "prefix": "n duration reference = 1 second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that s"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1969,
            "end": 2235,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change”. The reviewed quantity is observation duration = 1 second.",
            "prefix": "n duration reference = 1 second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that s"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2250,
            "end": 2494,
            "exact": "In equivalent wording, the document states that steady state is time independent, whereas dynamic equilibrium has equal forward and reverse reaction rates with no net composition change. The reviewed quantity is observation duration = 1 second.",
            "prefix": "ewed quantity is observation duration = 1 second.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA transient observation is not a time-i"
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
          "document_ref": "qualification-fixture:common:010",
          "document_digest": "sha256:fb116185338cb5c2d5440058c7c85b8505b365ddc294462ae24231a4d2a311ed",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2519,
            "end": 2676,
            "exact": "A transient observation is not a time-independent steady state in this definitions-only comparison. The reviewed quantity is observation duration = 1 second.",
            "prefix": "ity is observation duration = 1 second.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
