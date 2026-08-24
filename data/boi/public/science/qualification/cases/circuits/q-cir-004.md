---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CIR-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:circuits:004",
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
      "ref": "sci-rule:circuits:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:circuits:004",
    "standard_id": "Q-CIR-004",
    "rule_id": "sci-rule:circuits:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:circuits:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:clear_violation",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 162,
            "end": 333,
            "exact": "At fixed current under the passive sign convention, increasing a linear resistor's resistance makes its consumed power decrease. The current scale is recorded as 1 ampere.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nFor a linear resistor at fixed current "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:in_scope_consistency",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 358,
            "end": 538,
            "exact": "For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
            "prefix": " current scale is recorded as 1 ampere.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the sign conve"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:missing_required_condition",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 569,
            "end": 809,
            "exact": "Without specifying the sign convention, the report asserts: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
            "prefix": "nt scale is recorded as 1 ampere.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a nonlinear element rather than "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:outside_validity_domain",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 837,
            "end": 1092,
            "exact": "For a nonlinear element rather than a linear resistor, the report asserts: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
            "prefix": "rrent scale is recorded as 1 ampere.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a particular resistor me"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:empirical_verification_required",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1128,
            "end": 1422,
            "exact": "For a particular resistor measured on a named tester, the report asserts: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. This named result requires measurement. The current scale is recorded as 1 ampere.",
            "prefix": "ale is recorded as 1 ampere.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "linear_resistor"
              },
              {
                "condition_id": "requested_fixed_current_power_observation",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:negation",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1435,
            "end": 1675,
            "exact": "Under the stated scientific conditions, it is not true that for a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
            "prefix": "urement. The current scale is recorded as 1 ampere.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nFor a linear resistor at fixed current under "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:unit_variation",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1694,
            "end": 1929,
            "exact": "For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The reviewed quantities are current scale = 1000 milliampere; current scale reference = 1 ampere.",
            "prefix": "R. The current scale is recorded as 1 ampere.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1000,
                "unit": "milliampere"
              },
              {
                "quantity_kind": "current_scale_reference",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "current_scale",
            "value": 1,
            "unit": "ampere"
          },
          {
            "quantity_kind": "current_scale",
            "value": 1000,
            "unit": "milliampere"
          }
        ]
      },
      {
        "case_id": "sci-case:circuits:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1961,
            "end": 2219,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R”. The reviewed quantity is current scale = 1 ampere.",
            "prefix": "rent scale reference = 1 ampere.\n\n[decision_changing_ambiguity]\n",
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
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
              "ambiguity:sci-rule:circuits:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:circuits:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1961,
            "end": 2219,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R”. The reviewed quantity is current scale = 1 ampere.",
            "prefix": "rent scale reference = 1 ampere.\n\n[decision_changing_ambiguity]\n",
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
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
              "ambiguity:sci-rule:circuits:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:circuits:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:paraphrase",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2234,
            "end": 2458,
            "exact": "In equivalent wording, the document states: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
            "prefix": "he reviewed quantity is current scale = 1 ampere.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAn active current-controlled element is"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:electric-power",
          "sci-evidence:circuits:ohm-model"
        ]
      },
      {
        "case_id": "sci-case:circuits:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:circuits:004",
        "evaluation_rule_id": "sci-rule:circuits:004",
        "claim_packet": {
          "claim_id": "claim:circuits:004:false_red_prevention",
          "document_ref": "qualification-fixture:circuits:004",
          "document_digest": "sha256:557a6442268e7e32e5c02da05bc6b456544913101debd0d355f919fffd03d4b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2483,
            "end": 2632,
            "exact": "An active current-controlled element is reported to draw less power when its effective resistance changes. The current scale is recorded as 1 ampere.",
            "prefix": " current scale is recorded as 1 ampere.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:resistance",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:electric-power",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "sign_convention",
                "value": "passive"
              },
              {
                "condition_id": "current_held",
                "value": "fixed"
              },
              {
                "condition_id": "element_model",
                "value": "active_current_controlled_element"
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
        "rationale": "This natural-language claim exercises resistor power at fixed current through the target Rule's own typed conditions and Evidence scope.",
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

# Q-CIR-004

Ten public natural-claim fixtures qualify only `sci-rule:circuits:004`. No operational authority is created.
