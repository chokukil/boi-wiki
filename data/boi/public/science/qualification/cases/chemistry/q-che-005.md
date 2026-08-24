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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:d5725a4e1e9e868bb04b9146fcc15115a808ccdd6b4e043afbecfc3cf1486fc7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 138,
            "exact": "Adding a catalyst increases the equilibrium constant because it speeds the reaction. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:46baf9838af49ffd9a764f9032a9b254618c999c9302b742ccb9e0bfa29df33c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 198,
            "exact": "Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:cf293b3d0577659862614eb6e989f4f175c7e09c1e4e8eec75987acab56c1685",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 271,
            "exact": "Without specifying the balanced reaction comparison, the report asserts: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:dc1dd9d586300abe1b04e85ff2c13d161ddfec480b00a94a69cde72dcba9dfd1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 273,
            "exact": "When temperature changes along with catalyst addition, the report asserts: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:fc43c37f6fb115a389a854e61fabaac01bedca27f5a6ec3d1e57bde01eb43066",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 293,
            "exact": "For a named catalytic reactor run, the report asserts: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. This named result requires measurement. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:848a613441ad239ad9e1e60ee2f4292e27d3cfe819ee5350dcfb58dfe44808e9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 258,
            "exact": "Under the stated scientific conditions, it is not true that adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:ca4431e986bde66ba10e2ce88a0f9ef98ecc0e5b77c3a9310cb6ac491fc172ac",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 25 °C.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:3fd6aa5aadb9df912a0f402fcd77929a3bf0cb30ba3121775ab7dc079b7448ae",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 336,
            "exact": "The wording leaves unresolved whether 'Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature.' or instead 'Adding a catalyst increases the equilibrium constant because it speeds the reaction'. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:3fd6aa5aadb9df912a0f402fcd77929a3bf0cb30ba3121775ab7dc079b7448ae",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 336,
            "exact": "The wording leaves unresolved whether 'Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature.' or instead 'Adding a catalyst increases the equilibrium constant because it speeds the reaction'. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:685925cf9ac94307c2f80ca2760ca008b163f01f94a493fdc91d9a52ea17f19a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 242,
            "exact": "In equivalent wording, the document states: Adding a catalyst changes reaction kinetics but does not change the equilibrium constant for the same balanced reaction at the same temperature. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:005",
          "document_digest": "sha256:a298215aa507b5c64d10f0b5f7d1bfc07bc0a2b4e291d465eb6d615b80017f35",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 199,
            "exact": "When the temperature comparison is outside this rule's required scope, the document states that catalyst addition increases equilibrium constant. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_same_absolute_temperature"
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
