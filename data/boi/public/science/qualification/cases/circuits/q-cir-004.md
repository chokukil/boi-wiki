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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:f08520ae8d438d79ee43d6e97977e143f229e84605f4c102d6effddd4ece4846",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 171,
            "exact": "At fixed current under the passive sign convention, increasing a linear resistor's resistance makes its consumed power decrease. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:32e2d586324cd6bb433f1ca0f066f11aab5182a953709163f1ebc00ab7aceadf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 180,
            "exact": "For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:15bcc0666b0871403b10122ba8b07e5b748be7532e053f560a846aa587350dc0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 240,
            "exact": "Without specifying the sign convention, the report asserts: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:7f1176b38f6660f43fb32a2cdf0852ce4f32c00b87ca045741a44421f0eac47d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 255,
            "exact": "For a nonlinear element rather than a linear resistor, the report asserts: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:e2795edb1fbbb2db0a638ad0d41aa71c9aba59a14dc7d8464ebe2e423a228616",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 294,
            "exact": "For a particular resistor measured on a named tester, the report asserts: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. This named result requires measurement. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:e6ef544d818f831b5c9fce8be9418ad45b18b6abf2befb85dff7055a91347533",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 240,
            "exact": "Under the stated scientific conditions, it is not true that for a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:4e067c62a38c73470c45162c33be60ce21f74ce1c9d64737812a14601a522979",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 238,
            "exact": "For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1000 milliampere. The same current scale is referenced as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:c772fb1430efc114ed9b7221b374c5f1454d94cfc88c302f42789a700e9d1231",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 362,
            "exact": "The wording leaves unresolved whether 'For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R.' or instead 'At fixed current under the passive sign convention, increasing a linear resistor's resistance makes its consumed power decrease'. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:c772fb1430efc114ed9b7221b374c5f1454d94cfc88c302f42789a700e9d1231",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 362,
            "exact": "The wording leaves unresolved whether 'For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R.' or instead 'At fixed current under the passive sign convention, increasing a linear resistor's resistance makes its consumed power decrease'. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:d6664ab9e3bea703d964beabab39ee02e82747f025b41707b19fbcc798b053bc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 224,
            "exact": "In equivalent wording, the document states: For a linear resistor at fixed current under the passive sign convention, increasing resistance increases consumed power through P = I²R. The current scale is recorded as 1 ampere.",
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
          "document_ref": "qualification:circuits:004",
          "document_digest": "sha256:7d1d544165316fb7dad75fae716f77356443a27da849b4cf0e4d5f323ce4bdc4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 149,
            "exact": "An active current-controlled element is reported to draw less power when its effective resistance changes. The current scale is recorded as 1 ampere.",
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
