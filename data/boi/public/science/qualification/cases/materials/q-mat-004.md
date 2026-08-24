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
          "document_digest": "sha256:a14ca0d223ced2a99d4938d8591395076811a0f3ac6d0498c5a71c21d1dc4c92",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 366,
            "exact": "Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:cb668c2eba142716721681af76c2179e90a832d119aa174699ca0223e91b4972",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 379,
            "exact": "For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:a7b7912e3dfe15be23f6a055fd49ea1d146638eae9163cabf1ffd0c5806619ae",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 439,
            "exact": "Without specifying the diffusion model, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
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
          "document_digest": "sha256:f3c8665185a4906952056428f2273baeeebd97b4a5f6bdcd94e290c5c33342ad",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 478,
            "exact": "After the diffusion mechanism changes outside the qualified temperature range, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:370330cea6b78cc2a6f2f1b229ecd9087f842cf90374385ae0ca24804bd7f13e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 477,
            "exact": "For a named material and furnace run, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. This named result requires measurement. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "unchanged"
              },
              {
                "condition_id": "requested_diffusivity_temperature_observation",
                "value": "unqualified_observation"
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
          "document_digest": "sha256:61b43fec6d0f392eabcd22363ed4cf6183349b2bfe842fe45a69beaa2ae94fd4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 439,
            "exact": "Under the stated scientific conditions, it is not true that for positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:d372c975dc34240921acced01b5858dd4d54dbd8a5fec45a79cc329d40e743bc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 455,
            "exact": "For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 10000 centimeter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second. The same diffusivity scale is referenced as 1 meter ** 2 / second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_scale_reference",
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
          "document_digest": "sha256:128b835a181d07982f5bd727a6edaa3a1d99db21102ce4aeb6ab25acb80fb8aa",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 579,
            "exact": "The wording leaves unresolved whether 'For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient.' or instead 'Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged'. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:128b835a181d07982f5bd727a6edaa3a1d99db21102ce4aeb6ab25acb80fb8aa",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 579,
            "exact": "The wording leaves unresolved whether 'For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient.' or instead 'Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged'. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:376a50b53a51b06f82b49f855adbde5aac6f1f08414c66525e755987ccc2e8f0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 423,
            "exact": "In equivalent wording, the document states: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
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
          "document_digest": "sha256:de1c2cc0f324985ea5f0f1f941e6e14f106b5dda318953e37ce8364512991d4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 329,
            "exact": "After the diffusion mechanism changed, the measured diffusion coefficient decreased as temperature increased. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
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
              },
              {
                "quantity_kind": "activation_energy",
                "value": 1,
                "unit": "electron_volt"
              },
              {
                "quantity_kind": "temperature_before",
                "value": 300,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "temperature_after",
                "value": 350,
                "unit": "kelvin"
              },
              {
                "quantity_kind": "diffusivity_before",
                "value": "1e-15",
                "unit": "meter ** 2 / second"
              },
              {
                "quantity_kind": "diffusivity_after",
                "value": "5e-15",
                "unit": "meter ** 2 / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "diffusion_model",
                "value": "arrhenius"
              },
              {
                "condition_id": "mechanism_comparison",
                "value": "changed"
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
