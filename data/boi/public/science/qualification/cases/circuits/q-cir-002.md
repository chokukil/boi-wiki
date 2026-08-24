---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CIR-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:circuits:002",
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
      "ref": "sci-rule:circuits:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:circuits:002",
    "standard_id": "Q-CIR-002",
    "rule_id": "sci-rule:circuits:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:circuits:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:clear_violation",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 162,
            "end": 309,
            "exact": "The algebraic voltage sum around the defined lumped-circuit loop is 2 volts but is asserted to equal zero. The voltage scale is recorded as 1 volt.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe algebraic voltage sum around the de"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 2,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:in_scope_consistency",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 334,
            "end": 451,
            "exact": "The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "he voltage scale is recorded as 1 volt.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report omits a required scien"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:missing_required_condition",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 482,
            "end": 663,
            "exact": "The report omits a required scientific condition while stating: The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "tage scale is recorded as 1 volt.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor an undefined distributed path, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:outside_validity_domain",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 691,
            "end": 862,
            "exact": "For an undefined distributed path, the report states: The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "voltage scale is recorded as 1 volt.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named instrumented cir"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "outside_lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:empirical_verification_required",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 898,
            "end": 1112,
            "exact": "For a named instrumented circuit loop, the report states: The algebraic voltage sum around the defined lumped-circuit loop is 0 volts; the named result requires measurement. The voltage scale is recorded as 1 volt.",
            "prefix": "scale is recorded as 1 volt.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nThe report denies the equality even though the alge"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "requested_loop_voltage_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:negation",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1125,
            "end": 1285,
            "exact": "The report denies the equality even though the algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "asurement. The voltage scale is recorded as 1 volt.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe algebraic voltage sum around the defined "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:unit_variation",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1304,
            "end": 1474,
            "exact": "The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The reviewed quantities are voltage scale = 1000 millivolt; voltage scale reference = 1 volt.",
            "prefix": "lts. The voltage scale is recorded as 1 volt.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1000,
                "unit": "millivolt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "voltage_scale_reference",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "voltage_scale",
            "value": 1,
            "unit": "volt"
          },
          {
            "quantity_kind": "voltage_scale",
            "value": 1000,
            "unit": "millivolt"
          }
        ]
      },
      {
        "case_id": "sci-case:circuits:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1506,
            "end": 1759,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The algebraic voltage sum around the defined lumped-circuit loop is 0 volts”. The reviewed quantities are voltage scale = 1 volt; algebraic voltage sum = 0 volt; zero voltage = 0 volt.",
            "prefix": "oltage scale reference = 1 volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, the algebraic voltage s"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
              "ambiguity:sci-rule:circuits:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:circuits:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1506,
            "end": 1759,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The algebraic voltage sum around the defined lumped-circuit loop is 0 volts”. The reviewed quantities are voltage scale = 1 volt; algebraic voltage sum = 0 volt; zero voltage = 0 volt.",
            "prefix": "oltage scale reference = 1 volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, the algebraic voltage s"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 2,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
              "ambiguity:sci-rule:circuits:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:circuits:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:paraphrase",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1774,
            "end": 1917,
            "exact": "Using equivalent wording, the algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "raic voltage sum = 0 volt; zero voltage = 0 volt.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nVoltages along an open circuit path are"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 0,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "bound_closed_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:circuits:002",
        "evaluation_rule_id": "sci-rule:circuits:002",
        "claim_packet": {
          "claim_id": "claim:circuits:002:false_red_prevention",
          "document_ref": "qualification-fixture:circuits:002",
          "document_digest": "sha256:32af598203daab396fbbe7e5d21ad9d226bfe8ecbd00dd5638429cb7a4c3edba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1942,
            "end": 2074,
            "exact": "Voltages along an open circuit path are not the algebraic sum around a defined closed loop. The voltage scale is recorded as 1 volt.",
            "prefix": "he voltage scale is recorded as 1 volt.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:loop-voltage-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-voltage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              },
              {
                "quantity_kind": "algebraic_voltage_sum",
                "value": 2,
                "unit": "volt"
              },
              {
                "quantity_kind": "zero_voltage",
                "value": 0,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "loop_path",
                "value": "open_path"
              },
              {
                "condition_id": "circuit_context",
                "value": "lumped_loop"
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
        "rationale": "This natural-language claim exercises kirchhoff voltage law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kvl-law"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CIR-002

Ten public natural-claim fixtures qualify only `sci-rule:circuits:002`. No operational authority is created.
