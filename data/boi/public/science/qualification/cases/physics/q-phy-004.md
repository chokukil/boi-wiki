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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:c9f66806a3c38097f693aa0aaf8a6dfa36b49a19c85c1db2cbd67c1cc5bdeae5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 123,
            "exact": "A nonzero applied shear stress makes a simple fluid stop deforming. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:aff46757881585bcc2e1e39e1007c189686d3db1238807f6f63fa7121ce0d022",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:f8874f75d450e27a9c6de77922cf54416b10482b59ef7e1c02462cac9aea7c30",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 252,
            "exact": "Without specifying the material response class, the report asserts: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:98c444cd8e8c779047e91e30f2a9cd81e470bf15e35434ca10f379cbd67c95a2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 267,
            "exact": "For a solid-like material outside the simple-fluid definition, the report asserts: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:fd128a059513b7f86ee516de383f101e3e9042de58912bc8ac2be45116c48dcf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 284,
            "exact": "For a named rheometer and fluid sample, the report asserts: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. This named result requires measurement. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:dd24b835fb406f2b72ab2c503e72684d65748f0ce42b631e67c27d00d3f13bab",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 244,
            "exact": "Under the stated scientific conditions, it is not true that a simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:e4183081a00c33a6d088f804f060427776e1367d92d0caf35befd3facf63c42e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 255,
            "exact": "A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1000 millipascal * second. The same dynamic viscosity is referenced as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:2bbe7d9521341c229ed444aea3144e65793585d562f58c7ea3d01a6c8afcd976",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 305,
            "exact": "The wording leaves unresolved whether 'A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response.' or instead 'A nonzero applied shear stress makes a simple fluid stop deforming'. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:2bbe7d9521341c229ed444aea3144e65793585d562f58c7ea3d01a6c8afcd976",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 305,
            "exact": "The wording leaves unresolved whether 'A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response.' or instead 'A nonzero applied shear stress makes a simple fluid stop deforming'. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:a2be8caae66d6dd7aae7402adc214e0db444477fa01220a641413542f901d2dc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 228,
            "exact": "In equivalent wording, the document states: A simple fluid continues to deform while any shear stress is applied; a finite static shear strain is not its defining response. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:004",
          "document_digest": "sha256:df481d924974492d187b13a18073e6773748f16b53d05d9921ccd93283225336",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 129,
            "exact": "With zero applied shear stress, the sample is reported to stop deforming. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
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
