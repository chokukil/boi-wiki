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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:4610229f1c3b8e8c99bc8236959d2fecd3907e2d2bd184d80a2a4b3faacbcdc5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 104,
            "exact": "Applying forward bias increases the pn-junction barrier height. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:870bd2074da2bc5747690a6afc03f115006ded0213a7205c8264094de8f99d8c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 182,
            "exact": "Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:6ef535a76269d05cfe949fd7f1e0c7cc2495ea9fed6da6fe6ee1f890de2bab30",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 240,
            "exact": "Without specifying the junction type, the report asserts: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:10bf64430f8a83c935cf4ac7557a03ab2eae7dcb511e186b02abc76c8b12eb15",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 242,
            "exact": "Under reverse rather than forward bias, the report asserts: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:ba257d75730d20f4aadcae4488c4cced83a481fb392ff822aeeb5458b55db15b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 274,
            "exact": "For a named pn diode structure, the report asserts: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. This named result requires measurement. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:36a89497955149fee390987c244a18994c169293df08d50aa456890b3c063b9f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 242,
            "exact": "Under the stated scientific conditions, it is not true that applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:272b7b4fd2fba310c1114f37f65560baf156b10f59e9fd81c7971400470a50c3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1000 millivolt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:fb2c1a4f9bc2feb236948d0c1cb562cdbd6f8dacfa1e06ffa1a6d2002182b806",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 299,
            "exact": "The wording leaves unresolved whether 'Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance.' or instead 'Applying forward bias increases the pn-junction barrier height'. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:fb2c1a4f9bc2feb236948d0c1cb562cdbd6f8dacfa1e06ffa1a6d2002182b806",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 299,
            "exact": "The wording leaves unresolved whether 'Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance.' or instead 'Applying forward bias increases the pn-junction barrier height'. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:67cdd46bd1ea55beb9bdc13c57e2ad9cc867f623c17e7f8425432dd73777ed37",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 226,
            "exact": "In equivalent wording, the document states: Applying forward bias to a pn junction reduces its barrier height from the built-in value and disturbs the zero-bias drift-diffusion balance. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:semiconductor-devices:004",
          "document_digest": "sha256:c59910b045efc090c66521a196b44e0c99180038e45a580459aaecc16e76cfd0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 171,
            "exact": "When the bias polarity is outside this rule's required scope, the document states that forward bias increases pn junction barrier. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_forward"
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
