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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:1f64bf20cf3d3a989b73b1ed04da0f5cd097a1758f4f34fd872856016dc7900b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 169,
            "exact": "At fixed voltage under the passive sign convention, increasing a linear resistor's resistance makes its consumed power increase. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:9ed8b25227661cbb8f269d482ab684e16e2b25c463cecaf65bcd7fa7be74256b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 179,
            "exact": "For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:6d5dde70be0672b6ed6cedf9d40e7db023c8f5e2dc44890576b64cdb7d510846",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 239,
            "exact": "Without specifying the sign convention, the report asserts: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:f5075d3d480957cb89c26456ede13b907ed56c65132fe11615438db13af0c267",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 254,
            "exact": "For a nonlinear element rather than a linear resistor, the report asserts: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:828c59f4cdf1f4ad8036694139b2accd5bafc337c7f4998ed03102d59687fcc9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 293,
            "exact": "For a particular resistor measured on a named tester, the report asserts: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. This named result requires measurement. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:51e0a36e48da19af2aa5749206f1ebca8ef974be218a4eb2ba34cbf116f631f7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 239,
            "exact": "Under the stated scientific conditions, it is not true that for a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:eac69c8a91a312cbd3119e3e479534ad4b0abfd118f4a6920cd5f5484e102848",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 235,
            "exact": "For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1000 millivolt. The same voltage scale is referenced as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:16f466b07aef084aca24591b84e7e0d27ca7fc21dfae57f175e5b3f3f5bec382",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 361,
            "exact": "The wording leaves unresolved whether 'For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R.' or instead 'At fixed voltage under the passive sign convention, increasing a linear resistor's resistance makes its consumed power increase'. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:16f466b07aef084aca24591b84e7e0d27ca7fc21dfae57f175e5b3f3f5bec382",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 361,
            "exact": "The wording leaves unresolved whether 'For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R.' or instead 'At fixed voltage under the passive sign convention, increasing a linear resistor's resistance makes its consumed power increase'. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:06680f628c78130ab61bb114e2477941bd623709d35051bced1a997bde2ed3e3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 223,
            "exact": "In equivalent wording, the document states: For a linear resistor at fixed voltage under the passive sign convention, increasing resistance decreases consumed power through P = V²/R. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:003",
          "document_digest": "sha256:3753c4ed9e4a14a3308f945b81dfc701e0e36082a72bf9318138d33c3915e1b2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 166,
            "exact": "A nonlinear resistor outside the linear-resistor model is reported to draw more power after its operating resistance changes. The voltage scale is recorded as 1 volt.",
            "prefix": "",
            "suffix": ""
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
