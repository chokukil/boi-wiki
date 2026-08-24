---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-MAT-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:materials:004",
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
      "ref": "sci-rule:materials:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:materials:004",
    "standard_id": "Q-MAT-004",
    "rule_id": "sci-rule:materials:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:materials:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:clear_violation",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:4f253df72d7814ad5b4b90dfa08966d0b796cb2b186a1619954b32b4a3489211",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 206,
            "exact": "Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:in_scope_consistency",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:bd6b0c469aae06f168db78b4223c86c3a8cdfa09baf816f78e7914a2a5ed46e8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 219,
            "exact": "For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:missing_required_condition",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:3699d819c6be850e55eab384dd318cea169d45f4f2a95545a082b575334cbf38",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 279,
            "exact": "Without specifying the diffusion model, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:outside_validity_domain",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:c3f6716d3b66b1f436cd22288882b3a2df38983edcfbfd0624c8d6064c322e35",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 318,
            "exact": "After the diffusion mechanism changes outside the qualified temperature range, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "outside_qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:empirical_verification_required",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:11cd32adce3ee88cdb6cd7c7ba080b5f7c5ea5339e9388a70252c0b214740956",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 317,
            "exact": "For a named material and furnace run, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. This named result requires measurement. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:negation",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:475c15aed59b6df5275bb1ca9eb5564dc6d8f64f382df901d5ae84ecb1ea7eb0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 279,
            "exact": "Under the stated scientific conditions, it is not true that for positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:unit_variation",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:c6542a30dfcec34d75f28138b6fee62444f1cd35a68073eb46e4b39bcb5cf23b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 228,
            "exact": "For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 10000 centimeter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 10000,
                "unit": "centimeter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "diffusivity_scale",
            "value": 1,
            "unit": "meter ** 2 / second"
          },
          {
            "quantity_kind": "diffusivity_scale",
            "value": 10000,
            "unit": "centimeter ** 2 / second"
          }
        ]
      },
      {
        "case_id": "sci-case:materials:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:decision_changing_ambiguity",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:4681e1b3054a57d2732a09c4cc225aee3238c37e4e116d3752f6d1a8b7e2b3e5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 419,
            "exact": "The wording leaves unresolved whether 'For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient.' or instead 'Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged'. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:materials:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:materials:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:4681e1b3054a57d2732a09c4cc225aee3238c37e4e116d3752f6d1a8b7e2b3e5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 419,
            "exact": "The wording leaves unresolved whether 'For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient.' or instead 'Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged'. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:materials:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:materials:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:paraphrase",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:ba19540b50f8645adbe05261a249dedf86530f7a7feab3e957dc96dea3216042",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 263,
            "exact": "In equivalent wording, the document states: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      },
      {
        "case_id": "sci-case:materials:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:materials:004",
        "evaluation_rule_id": "sci-rule:materials:004",
        "claim_packet": {
          "claim_id": "claim:materials:004:false_red_prevention",
          "document_ref": "qualification:materials:004",
          "document_digest": "sha256:06a40cc0824a0c653bcd761f6ceb6bc154ee2be4eabda6ac3e26c8bc2279a533",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 207,
            "exact": "When the mechanism comparison is outside this rule's required scope, the document states that absolute temperature decreases diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:absolute-temperature",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:diffusion-coefficient",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "diffusivity_scale",
                "value": 1,
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "material_parameters_known",
                "value": true
              },
              {
                "condition_id": "activation_energy_sign",
                "value": "positive"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "outside_unchanged"
              },
              {
                "condition_id": "temperature_domain",
                "value": "qualified_range"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:bulk-property",
              "sci:binding:domain:thin-film-property"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises arrhenius diffusion temperature direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:diffusion-arrhenius"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-MAT-004

Ten public natural-claim fixtures qualify only `sci-rule:materials:004`. No operational authority is created.
