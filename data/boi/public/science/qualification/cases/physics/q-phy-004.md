---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-PHY-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:physics:004",
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
      "ref": "sci-rule:physics:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:physics:004",
    "standard_id": "Q-PHY-004",
    "rule_id": "sci-rule:physics:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:physics:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:clear_violation",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 161,
            "end": 284,
            "exact": "A nonzero applied shear stress makes a simple fluid stop deforming. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA simple fluid continues to deform whil"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "stops",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:in_scope_consistency",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 309,
            "end": 493,
            "exact": "A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "osity is recorded as 1 pascal * second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the material r"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:missing_required_condition",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 524,
            "end": 776,
            "exact": "Without specifying the material response class, the report asserts: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "is recorded as 1 pascal * second.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a solid-like material outside th"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:outside_validity_domain",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 804,
            "end": 1071,
            "exact": "For a solid-like material outside the simple-fluid definition, the report asserts: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "ty is recorded as 1 pascal * second.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named rheometer and fl"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "outside_continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:empirical_verification_required",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1107,
            "end": 1391,
            "exact": "For a named rheometer and fluid sample, the report asserts: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. This named result requires measurement. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "corded as 1 pascal * second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "requested_fluid_deformation_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:negation",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1404,
            "end": 1648,
            "exact": "Under the stated scientific conditions, it is not true that a simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "dynamic viscosity is recorded as 1 pascal * second.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA simple fluid continues to deform while any "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:unit_variation",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1667,
            "end": 1919,
            "exact": "A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The reviewed quantities are dynamic viscosity = 1000 millipascal * second; dynamic viscosity reference = 1 pascal * second.",
            "prefix": "c viscosity is recorded as 1 pascal * second.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1000,
                "unit": "millipascal * second"
              },
              {
                "quantity_kind": "dynamic_viscosity_reference",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "dynamic_viscosity",
            "value": 1,
            "unit": "pascal * second"
          },
          {
            "quantity_kind": "dynamic_viscosity",
            "value": 1000,
            "unit": "millipascal * second"
          }
        ]
      },
      {
        "case_id": "sci-case:physics:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1951,
            "end": 2213,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response”. The reviewed quantity is dynamic viscosity = 1 pascal * second.",
            "prefix": "y reference = 1 pascal * second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: A sim"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:physics:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:physics:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1951,
            "end": 2213,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response”. The reviewed quantity is dynamic viscosity = 1 pascal * second.",
            "prefix": "y reference = 1 pascal * second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: A sim"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "stops",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:physics:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:physics:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:paraphrase",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2228,
            "end": 2456,
            "exact": "In equivalent wording, the document states: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "uantity is dynamic viscosity = 1 pascal * second.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nWith zero applied shear stress, the sam"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "continues",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "nonzero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      },
      {
        "case_id": "sci-case:physics:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:physics:004",
        "evaluation_rule_id": "sci-rule:physics:004",
        "claim_packet": {
          "claim_id": "claim:physics:004:false_red_prevention",
          "document_ref": "qualification-fixture:physics:004",
          "document_digest": "sha256:c6328bb84f576c43ec04f23a41a9c61ec6dd05c55c7b9cf66c8e22ae5350cbba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2481,
            "end": 2610,
            "exact": "With zero applied shear stress, the sample is reported to stop deforming. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "osity is recorded as 1 pascal * second.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:shear-stress",
            "relation_kind": "causal_relation",
            "predicate": "stops",
            "object_concept_id": "sci:concept:simple-fluid-deformation",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "dynamic_viscosity",
                "value": 1,
                "unit": "pascal * second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_response_class",
                "value": "simple_fluid"
              },
              {
                "condition_id": "shear_stress_state",
                "value": "zero_applied"
              },
              {
                "condition_id": "description_regime",
                "value": "continuum"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises simple fluid deforms under shear through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:viscosity-flow"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-PHY-004

Ten public natural-claim fixtures qualify only `sci-rule:physics:004`. No operational authority is created.
