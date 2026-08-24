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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:29465727929e38a0a62dceb6740981d74d567ca2f2b8a637b64009ceadd90a58",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 145,
            "exact": "Within the ideal MOS model, a perfectly insulating gate oxide requires nonzero gate current. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:6bafbc8e07097ba9e0ba2a7b669f29a01880770dc99cdfa346d4209b9b706540",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 217,
            "exact": "The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:81788dd6e4d1404abfccb8c28eb7d7a8c8075cb1170c319923515133548711a7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 274,
            "exact": "Without specifying the model regime, the report asserts: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:eda26c32e9067ed684c1addeda5294ae9888480083f6e818ab5ab77fc90d3c9a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 272,
            "exact": "For a real ultrathin-oxide device, the report asserts: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:d5fe70681d1d796127bae6c6c36189ca0cb65b9a3224ac005b6ae7dfeea94b0f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 315,
            "exact": "For a named idealized MOS simulation, the report asserts: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. This named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:5a7265654cc13d255eed5743a19e0937c304f03595d68b3c5d0aef5c04946cee",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 277,
            "exact": "Under the stated scientific conditions, it is not true that the ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:cfd042c4b53a318c4554150ec3837feec8d032e45d1b8ace12053b8f028608d9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 222,
            "exact": "The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 0.001 micrometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:2659c5d3a0d262e40d62d7e0e2b3f8dcd12ef07e32218acd5c6913b434c2ae13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 363,
            "exact": "The wording leaves unresolved whether 'The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices.' or instead 'Within the ideal MOS model, a perfectly insulating gate oxide requires nonzero gate current'. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:2659c5d3a0d262e40d62d7e0e2b3f8dcd12ef07e32218acd5c6913b434c2ae13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 363,
            "exact": "The wording leaves unresolved whether 'The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices.' or instead 'Within the ideal MOS model, a perfectly insulating gate oxide requires nonzero gate current'. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:e9b5cb97fd6040a1fae0290f084a356d4799cd727505c36f971e43f4f507fd61",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 261,
            "exact": "In equivalent wording, the document states: The ideal MOS model treats the oxide as insulating and therefore sets gate current to zero; this is a model statement, not a universal assertion about real devices. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:005",
          "document_digest": "sha256:dfa6b1334f8a624bff410d734e5ba0ee6b08bc2ce7979a17a41abafef1f8d8f5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 179,
            "exact": "When the gate oxide model is outside this rule's required scope, the document states that ideal mos gate nonzero gate current. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_perfect_insulator"
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
