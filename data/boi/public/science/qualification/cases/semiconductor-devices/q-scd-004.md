---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SCD-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:semiconductor-devices:004",
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
      "ref": "sci-rule:semiconductor-devices:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:semiconductor-devices:004",
    "standard_id": "Q-SCD-004",
    "rule_id": "sci-rule:semiconductor-devices:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:semiconductor-devices:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:clear_violation",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 175,
            "end": 279,
            "exact": "Applying forward bias increases the pn-junction barrier height. The voltage scale is recorded as 1 volt.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nApplying forward bias to a pn junction "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:in_scope_consistency",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 304,
            "end": 486,
            "exact": "Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "he voltage scale is recorded as 1 volt.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the junction t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:missing_required_condition",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 517,
            "end": 757,
            "exact": "Without specifying the junction type, the report asserts: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "tage scale is recorded as 1 volt.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nUnder reverse rather than forward bi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:outside_validity_domain",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 785,
            "end": 1027,
            "exact": "Under reverse rather than forward bias, the report asserts: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "voltage scale is recorded as 1 volt.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named pn diode structu"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "outside_pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:empirical_verification_required",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1063,
            "end": 1337,
            "exact": "For a named pn diode structure, the report asserts: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. This named result requires measurement. The voltage scale is recorded as 1 volt.",
            "prefix": "scale is recorded as 1 volt.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "requested_junction_barrier_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:negation",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1350,
            "end": 1592,
            "exact": "Under the stated scientific conditions, it is not true that applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "asurement. The voltage scale is recorded as 1 volt.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nApplying forward bias to a pn junction reduce"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:unit_variation",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1611,
            "end": 1846,
            "exact": "Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The reviewed quantities are voltage scale = 1000 millivolt; voltage scale reference = 1 volt.",
            "prefix": "nce. The voltage scale is recorded as 1 volt.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
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
        "case_id": "sci-case:semiconductor-devices:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1878,
            "end": 2138,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance”. The reviewed quantity is voltage scale = 1 volt.",
            "prefix": "oltage scale reference = 1 volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Apply"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
              "ambiguity:sci-rule:semiconductor-devices:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1878,
            "end": 2138,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance”. The reviewed quantity is voltage scale = 1 volt.",
            "prefix": "oltage scale reference = 1 volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: Apply"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
              "ambiguity:sci-rule:semiconductor-devices:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:paraphrase",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2153,
            "end": 2379,
            "exact": "In equivalent wording, the document states: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": " The reviewed quantity is voltage scale = 1 volt.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nUnder reverse bias, the junction-barrie"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "forward"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:semiconductor-devices:004",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:004",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:004:false_red_prevention",
          "document_ref": "qualification-fixture:semiconductor-devices:004",
          "document_digest": "sha256:d17341b98ea7eda85b26faf09afc6a9e4811c8d19d18e534e735e6a95f0fc222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2404,
            "end": 2553,
            "exact": "Under reverse bias, the junction-barrier response is not the forward-bias comparison addressed by this rule. The voltage scale is recorded as 1 volt.",
            "prefix": "he voltage scale is recorded as 1 volt.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:forward-bias",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:pn-junction-barrier",
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
                "condition_id": "junction_type",
                "value": "pn"
              },
              {
                "condition_id": "bias_polarity",
                "value": "reverse"
              },
              {
                "condition_id": "device_model",
                "value": "pn_junction_barrier"
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
        "rationale": "This natural-language claim exercises forward bias lowers a pn-junction barrier through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:pn-junction"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SCD-004

Ten public natural-claim fixtures qualify only `sci-rule:semiconductor-devices:004`. No operational authority is created.
