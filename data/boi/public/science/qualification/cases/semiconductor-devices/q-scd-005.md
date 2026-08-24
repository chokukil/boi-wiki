---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SCD-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:semiconductor-devices:005",
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
      "ref": "sci-rule:semiconductor-devices:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:semiconductor-devices:005",
    "standard_id": "Q-SCD-005",
    "rule_id": "sci-rule:semiconductor-devices:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:semiconductor-devices:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:clear_violation",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 175,
            "end": 320,
            "exact": "Within the ideal MOS model, a perfectly insulating gate oxide requires nonzero gate current. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe ideal MOS model treats the oxide as"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "nonzero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:in_scope_consistency",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 345,
            "end": 562,
            "exact": "The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the model regi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:missing_required_condition",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 593,
            "end": 867,
            "exact": "Without specifying the model regime, the report asserts: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "scale is recorded as 1 nanometer.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a real ultrathin-oxide device, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:outside_validity_domain",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 895,
            "end": 1167,
            "exact": "For a real ultrathin-oxide device, the report asserts: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ss scale is recorded as 1 nanometer.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named idealized MOS si"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "outside_ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:empirical_verification_required",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1203,
            "end": 1518,
            "exact": "For a named idealized MOS simulation, the report asserts: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. This named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": " is recorded as 1 nanometer.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "requested_ideal_gate_current_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:negation",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1531,
            "end": 1808,
            "exact": "Under the stated scientific conditions, it is not true that the ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "he film thickness scale is recorded as 1 nanometer.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe ideal MOS model treats the oxide as insul"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:unit_variation",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1827,
            "end": 2106,
            "exact": "The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The reviewed quantities are film thickness scale = 0.001 micrometer; film thickness scale reference = 1 nanometer.",
            "prefix": "m thickness scale is recorded as 1 nanometer.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": "0.001",
                "unit": "micrometer"
              },
              {
                "quantity_kind": "film_thickness_scale_reference",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "film_thickness_scale",
            "value": 1,
            "unit": "nanometer"
          },
          {
            "quantity_kind": "film_thickness_scale",
            "value": "0.001",
            "unit": "micrometer"
          }
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2138,
            "end": 2433,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: The i"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:semiconductor-devices:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2138,
            "end": 2433,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: The i"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "nonzero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:semiconductor-devices:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:paraphrase",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2448,
            "end": 2709,
            "exact": "In equivalent wording, the document states: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "d quantity is film thickness scale = 1 nanometer.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA tunneling dielectric is a physical no"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "zero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "perfect_insulator"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:semiconductor-devices:005",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:005",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:005:false_red_prevention",
          "document_ref": "qualification-fixture:semiconductor-devices:005",
          "document_digest": "sha256:888a4a48ae619a5c17d23f9174069087cdcc8fa7b117f5fcf0ad5c9c823f7085",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2734,
            "end": 2898,
            "exact": "A tunneling dielectric is a physical nonideal oxide, not the perfectly insulating oxide of the ideal MOS model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:ideal-mos-gate",
            "relation_kind": "causal_relation",
            "predicate": "nonzero",
            "object_concept_id": "sci:concept:gate-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "model_regime",
                "value": "ideal_mos"
              },
              {
                "condition_id": "gate_oxide_model",
                "value": "tunneling_dielectric"
              },
              {
                "condition_id": "claim_target",
                "value": "ideal_device"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises ideal mos gate-current model through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-ideal-model"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SCD-005

Ten public natural-claim fixtures qualify only `sci-rule:semiconductor-devices:005`. No operational authority is created.
