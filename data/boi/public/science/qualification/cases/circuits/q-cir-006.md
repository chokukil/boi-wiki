---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CIR-006 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:circuits:006",
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
      "ref": "sci-rule:circuits:006"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:circuits:006",
    "standard_id": "Q-CIR-006",
    "rule_id": "sci-rule:circuits:006",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:circuits:006:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:clear_violation",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:eebc6f72ef151731918bc2c730bbb8839d04dde51a36e86ef84ecd74a3d86f2d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 162,
            "exact": "Connecting a finite-impedance measuring instrument cannot change the observed circuit behavior under any circumstances. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "cannot_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:in_scope_consistency",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:a3cae570dcc3233e12733c740c7007134882507d2f01145b22767ac6e479b57d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:missing_required_condition",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:7cbfb5db7bc32ab115eef3abd3e1f64e938d83b1b63d96693952aa7ea3d649e1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "Without specifying the instrument connection, the report asserts: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:outside_validity_domain",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:9e103d7a97a956e5d1cc6352feec38b69ffc2dcdac794823fee69b0845755259",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "For an idealized infinite-impedance observer, the report asserts: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "outside_electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:empirical_verification_required",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:97fc7f766c8a57c74d0a4e641e4f2bfdd8e8214de4a542e7b75b89d590cf765b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 261,
            "exact": "For a named oscilloscope and circuit, the report asserts: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. This named result requires measurement. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "requested_instrument_loading_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:negation",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:25e987557ddc2cb82984d639ddb4e86ef97ddd83df4095f34534c81abe240719",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 223,
            "exact": "Under the stated scientific conditions, it is not true that connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:unit_variation",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:480540c0607b7248b45c027a865ed80c9e3b027ae831aaee0fa8d828ec56fd9a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 221,
            "exact": "Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1000 milliohm. The same resistance scale is referenced as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1000,
                "unit": "milliohm"
              },
              {
                "quantity_kind": "resistance_scale_reference",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "resistance_scale",
            "value": 1,
            "unit": "ohm"
          },
          {
            "quantity_kind": "resistance_scale",
            "value": 1000,
            "unit": "milliohm"
          }
        ]
      },
      {
        "case_id": "sci-case:circuits:006:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:decision_changing_ambiguity",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:6bdd12291aa13295ca64d1bfd164ed2a75dbbad7fccb25993ee6d166c4c2ee3b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 336,
            "exact": "The wording leaves unresolved whether 'Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading.' or instead 'Connecting a finite-impedance measuring instrument cannot change the observed circuit behavior under any circumstances'. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:circuits:006:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:circuits:006:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:6bdd12291aa13295ca64d1bfd164ed2a75dbbad7fccb25993ee6d166c4c2ee3b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 336,
            "exact": "The wording leaves unresolved whether 'Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading.' or instead 'Connecting a finite-impedance measuring instrument cannot change the observed circuit behavior under any circumstances'. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "cannot_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:circuits:006:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:circuits:006:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:paraphrase",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:0152179f8691d9c7d248b06386c1bd45a9bcf0495674b0e229dcd2371b16c03a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 207,
            "exact": "In equivalent wording, the document states: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "can_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "finite"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      },
      {
        "case_id": "sci-case:circuits:006:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:circuits:006",
        "evaluation_rule_id": "sci-rule:circuits:006",
        "claim_packet": {
          "claim_id": "claim:circuits:006:false_red_prevention",
          "document_ref": "qualification:circuits:006",
          "document_digest": "sha256:673d43894380e973dbd77267e9bab04bc1a5121419d98834c9bd2984c2550251",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 135,
            "exact": "An ideal voltmeter with infinite input impedance is stated not to load the measured circuit. The resistance scale is recorded as 1 ohm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-instrument-connection",
            "relation_kind": "causal_relation",
            "predicate": "cannot_change",
            "object_concept_id": "sci:concept:circuit-behavior",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "resistance_scale",
                "value": 1,
                "unit": "ohm"
              }
            ],
            "conditions": [
              {
                "condition_id": "instrument_connection",
                "value": "connected_to_circuit"
              },
              {
                "condition_id": "input_impedance",
                "value": "infinite_ideal"
              },
              {
                "condition_id": "coupling_path",
                "value": "electrical"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises measurement loading through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:measurement-loading"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CIR-006

Ten public natural-claim fixtures qualify only `sci-rule:circuits:006`. No operational authority is created.
