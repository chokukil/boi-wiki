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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 162,
            "end": 324,
            "exact": "Connecting a finite-impedance measuring instrument cannot change the observed circuit behavior under any circumstances. The resistance scale is recorded as 1 ohm.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nConnecting a finite-impedance measuring"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 349,
            "end": 512,
            "exact": "Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": " resistance scale is recorded as 1 ohm.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the instrument"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 543,
            "end": 772,
            "exact": "Without specifying the instrument connection, the report asserts: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "tance scale is recorded as 1 ohm.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor an idealized infinite-impedance "
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 800,
            "end": 1029,
            "exact": "For an idealized infinite-impedance observer, the report asserts: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "sistance scale is recorded as 1 ohm.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named oscilloscope and"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1065,
            "end": 1326,
            "exact": "For a named oscilloscope and circuit, the report asserts: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. This named result requires measurement. The resistance scale is recorded as 1 ohm.",
            "prefix": " scale is recorded as 1 ohm.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1339,
            "end": 1562,
            "exact": "Under the stated scientific conditions, it is not true that connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "urement. The resistance scale is recorded as 1 ohm.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nConnecting a finite-impedance measuring instr"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1581,
            "end": 1799,
            "exact": "Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The reviewed quantities are resistance scale = 1000 milliohm; resistance scale reference = 1 ohm.",
            "prefix": "g. The resistance scale is recorded as 1 ohm.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1831,
            "end": 2072,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading”. The reviewed quantity is resistance scale = 1 ohm.",
            "prefix": "istance scale reference = 1 ohm.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Conne"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1831,
            "end": 2072,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading”. The reviewed quantity is resistance scale = 1 ohm.",
            "prefix": "istance scale reference = 1 ohm.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Conne"
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2087,
            "end": 2294,
            "exact": "In equivalent wording, the document states: Connecting a finite-impedance measuring instrument can change the external circuit behavior through measurement loading. The resistance scale is recorded as 1 ohm.",
            "prefix": "he reviewed quantity is resistance scale = 1 ohm.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAn ideal voltmeter with infinite input "
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
          "document_ref": "qualification-fixture:circuits:006",
          "document_digest": "sha256:16693d0af0197e10db814d9e8a02365dc23452c0c20898e85f59444fd5013400",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2319,
            "end": 2454,
            "exact": "An ideal voltmeter with infinite input impedance is stated not to load the measured circuit. The resistance scale is recorded as 1 ohm.",
            "prefix": " resistance scale is recorded as 1 ohm.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
