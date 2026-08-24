---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CHE-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:chemistry:005",
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
      "ref": "sci-rule:chemistry:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:chemistry:005",
    "standard_id": "Q-CHE-005",
    "rule_id": "sci-rule:chemistry:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:chemistry:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:clear_violation",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 301,
            "exact": "Adding a catalyst increases the equilibrium constant because it speeds the reaction. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nAdding a catalyst changes reaction kine"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "increases",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:in_scope_consistency",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 326,
            "end": 524,
            "exact": "Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "mperature is recorded as 298.15 kelvin.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the balanced r"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:missing_required_condition",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 555,
            "end": 826,
            "exact": "Without specifying the balanced reaction comparison, the report asserts: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "ure is recorded as 298.15 kelvin.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nWhen temperature changes along with "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:outside_validity_domain",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 854,
            "end": 1127,
            "exact": "When temperature changes along with catalyst addition, the report asserts: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "rature is recorded as 298.15 kelvin.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named catalytic reacto"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "outside_catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:empirical_verification_required",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1163,
            "end": 1456,
            "exact": "For a named catalytic reactor run, the report asserts: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. This named result requires measurement. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "s recorded as 298.15 kelvin.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "requested_catalyst_equilibrium_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:negation",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1469,
            "end": 1727,
            "exact": "Under the stated scientific conditions, it is not true that adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "e context temperature is recorded as 298.15 kelvin.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nAdding a catalyst changes reaction kinetics b"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:unit_variation",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1746,
            "end": 1994,
            "exact": "Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The reviewed quantities are context temperature = 25 °C; context temperature reference = 298.15 kelvin.",
            "prefix": "ext temperature is recorded as 298.15 kelvin.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": 25,
                "unit": "°C"
              },
              {
                "quantity_kind": "context_temperature_reference",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "context_temperature",
            "value": "298.15",
            "unit": "kelvin"
          },
          {
            "quantity_kind": "context_temperature",
            "value": 25,
            "unit": "°C"
          }
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2026,
            "end": 2302,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature”. The reviewed quantity is context temperature = 298.15 kelvin.",
            "prefix": "ature reference = 298.15 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Addin"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:chemistry:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:chemistry:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2026,
            "end": 2302,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature”. The reviewed quantity is context temperature = 298.15 kelvin.",
            "prefix": "ature reference = 298.15 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Addin"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "increases",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:chemistry:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:chemistry:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:paraphrase",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2317,
            "end": 2559,
            "exact": "In equivalent wording, the document states: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": " quantity is context temperature = 298.15 kelvin.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAt different absolute temperatures, cat"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "unchanged",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "same_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:chemistry:005",
        "evaluation_rule_id": "sci-rule:chemistry:005",
        "claim_packet": {
          "claim_id": "claim:chemistry:005:false_red_prevention",
          "document_ref": "qualification-fixture:chemistry:005",
          "document_digest": "sha256:52dd333c581277d0bdeb55ff9212011d52c254373bd4ff490d7ed87231b3b8de",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2584,
            "end": 2765,
            "exact": "At different absolute temperatures, catalyst addition is not the only changed condition in the equilibrium-constant comparison. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "mperature is recorded as 298.15 kelvin.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:catalyst-addition",
            "relation_kind": "causal_relation",
            "predicate": "increases",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction_comparison",
                "value": "same_stoichiometry"
              },
              {
                "condition_id": "temperature_comparison",
                "value": "different_absolute_temperature"
              },
              {
                "condition_id": "comparison_change",
                "value": "catalyst_only"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises catalyst does not set equilibrium constant through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:catalyst-kinetics",
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CHE-005

Ten public natural-claim fixtures qualify only `sci-rule:chemistry:005`. No operational authority is created.
