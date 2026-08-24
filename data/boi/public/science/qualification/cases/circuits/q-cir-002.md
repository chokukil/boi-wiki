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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:f970ad2faf6b7e33511df0db1f87f22245d1f9a2d1aa35f16470b9de70ca1f85",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 147,
            "exact": "The algebraic voltage sum around the defined lumped-circuit loop is 2 volts but is asserted to equal zero. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:a14b44ca0ab7723f59ce081403aa45c62de6736769a14b518bb907d65f8a9632",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 117,
            "exact": "The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:7508fe55e78b352022c6d8b186cdb4ec05253a4a0201b065ce5f57b2dd1dfc68",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 181,
            "exact": "The report omits a required scientific condition while stating: The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:fe671564a752cbae2595240fac15abace6201d0c67f6216a62f6ee3d33715d5b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 171,
            "exact": "For an undefined distributed path, the report states: The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:dde4fd2efc84133ad3a1d49f6cdca6dbdba5a54f84b412a5dcf336f456de3bad",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 214,
            "exact": "For a named instrumented circuit loop, the report states: The algebraic voltage sum around the defined lumped-circuit loop is 0 volts; the named result requires measurement. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:ddc7c26c77783dafc79159543b3950ccc1765549977095bb289f024cdf2ef438",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "The report denies the equality even though the algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:b6e2e246d7bf81b7f28e8c4ddd531587c3811679ae409ccd4221f264a9ee0ed6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 173,
            "exact": "The algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1000 millivolt. The same voltage scale is referenced as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:5c3a9ed8386643c02f334f72a2e4d47ce06fcfdc5b1f7c3564b8fcd59e7cfd56",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 305,
            "exact": "A blurred table entry can be read as either 'The algebraic voltage sum around the defined lumped-circuit loop is 0 volts' or 'The algebraic voltage sum around the defined lumped-circuit loop is 2 volts but is asserted to equal zero', so the equation is unresolved. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:5c3a9ed8386643c02f334f72a2e4d47ce06fcfdc5b1f7c3564b8fcd59e7cfd56",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 305,
            "exact": "A blurred table entry can be read as either 'The algebraic voltage sum around the defined lumped-circuit loop is 0 volts' or 'The algebraic voltage sum around the defined lumped-circuit loop is 2 volts but is asserted to equal zero', so the equation is unresolved. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:c1fff4f61cfb3dd0730f73ab4e1e85e6d359b3dbe800ef634f53ca830fb21ab4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 143,
            "exact": "Using equivalent wording, the algebraic voltage sum around the defined lumped-circuit loop is 0 volts. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:002",
          "document_digest": "sha256:89b714baf7e0bc170d4eb16eaadd9efe00e62c83eb0e40e049d159b38934c57a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 132,
            "exact": "Voltages along an open circuit path are not the algebraic sum around a defined closed loop. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
