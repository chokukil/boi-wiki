---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CIR-003 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:circuits:003",
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
      "ref": "sci-rule:circuits:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:circuits:003",
    "standard_id": "Q-CIR-003",
    "rule_id": "sci-rule:circuits:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:circuits:003:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:clear_violation",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 162,
            "end": 331,
            "exact": "At fixed voltage under the passive sign convention, increasing a linear resistor's resistance makes its consumed power increase. The voltage scale is recorded as 1 volt.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nFor a linear resistor at fixed voltage "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:in_scope_consistency",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 356,
            "end": 535,
            "exact": "For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "he voltage scale is recorded as 1 volt.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the sign conve"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:missing_required_condition",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 566,
            "end": 805,
            "exact": "Without specifying the sign convention, the report asserts: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "tage scale is recorded as 1 volt.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a nonlinear element rather than "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:outside_validity_domain",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 833,
            "end": 1087,
            "exact": "For a nonlinear element rather than a linear resistor, the report asserts: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "voltage scale is recorded as 1 volt.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a particular resistor me"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "outside_steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:empirical_verification_required",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1123,
            "end": 1416,
            "exact": "For a particular resistor measured on a named tester, the report asserts: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. This named result requires measurement. The voltage scale is recorded as 1 volt.",
            "prefix": "scale is recorded as 1 volt.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "requested_fixed_voltage_power_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:negation",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1429,
            "end": 1668,
            "exact": "Under the stated scientific conditions, it is not true that for a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "asurement. The voltage scale is recorded as 1 volt.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nFor a linear resistor at fixed voltage under "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:unit_variation",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1687,
            "end": 1919,
            "exact": "For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The reviewed quantities are voltage scale = 1000 millivolt; voltage scale reference = 1 volt.",
            "prefix": "²/R. The voltage scale is recorded as 1 volt.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1000,
                "unit": "millivolt"
              },
              {
                "quantity_kind": "voltage_scale_reference",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
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
        "case_id": "sci-case:circuits:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1951,
            "end": 2208,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R”. The reviewed quantity is voltage scale = 1 volt.",
            "prefix": "oltage scale reference = 1 volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: For a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
              "ambiguity:sci-rule:circuits:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:circuits:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1951,
            "end": 2208,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R”. The reviewed quantity is voltage scale = 1 volt.",
            "prefix": "oltage scale reference = 1 volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: For a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
              "ambiguity:sci-rule:circuits:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:circuits:003:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:paraphrase",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2223,
            "end": 2446,
            "exact": "In equivalent wording, the document states: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": " The reviewed quantity is voltage scale = 1 volt.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA nonlinear resistor outside the linear"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:circuits:003",
        "evaluation_rule_id": "sci-rule:circuits:003",
        "claim_packet": {
          "claim_id": "claim:circuits:003:false_red_prevention",
          "document_ref": "qualification-fixture:circuits:003",
          "document_digest": "sha256:e396248a2b944aa25e63006e6b37d830ffded1d27198b0fccdef42a5acd06d77",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2471,
            "end": 2637,
            "exact": "A nonlinear resistor outside the linear-resistor model is reported to draw more power after its operating resistance changes. The voltage scale is recorded as 1 volt.",
            "prefix": "he voltage scale is recorded as 1 volt.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "voltage_scale",
                "value": 1,
                "unit": "volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "voltage_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "nonlinear_resistor"
              },
              {
                "condition_id": "operating_regime",
                "value": "steady_dc"
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
        "rationale": "This natural-language claim exercises resistor power at fixed voltage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CIR-003

Ten public natural-claim fixtures qualify only `sci-rule:circuits:003`. No operational authority is created.
