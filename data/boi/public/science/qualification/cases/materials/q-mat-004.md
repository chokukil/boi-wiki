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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 529,
            "exact": "Increasing absolute temperature decreases the Arrhenius diffusion coefficient while its positive activation energy and mechanism remain unchanged. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nFor positive activation energy and unch"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 554,
            "end": 933,
            "exact": "For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "e-15 and 5e-15 square meter per second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the diffusion "
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 964,
            "end": 1403,
            "exact": "Without specifying the diffusion model, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "nd 5e-15 square meter per second.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nAfter the diffusion mechanism change"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1431,
            "end": 1909,
            "exact": "After the diffusion mechanism changes outside the qualified temperature range, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "5 and 5e-15 square meter per second.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named material and fur"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1945,
            "end": 2422,
            "exact": "For a named material and furnace run, the report asserts: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. This named result requires measurement. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "-15 square meter per second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2435,
            "end": 2874,
            "exact": "Under the stated scientific conditions, it is not true that for positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "fusivities 1e-15 and 5e-15 square meter per second.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nFor a positive activation energy of 1 electro"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2893,
            "end": 3230,
            "exact": "For a positive activation energy of 1 electron volt and an unchanged Arrhenius mechanism, raising temperature from 300 kelvin to 350 kelvin raises diffusivity from 1e-15 to 5e-15 square metres per second. The reviewed quantities are diffusivity scale = 10000 centimeter ** 2 / second; diffusivity scale reference = 1 meter ** 2 / second.",
            "prefix": "ties 1e-15 and 5e-15 square meter per second.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 3262,
            "end": 3804,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a positive activation energy of 1 electron volt and an unchanged Arrhenius mechanism, raising temperature from 300 kelvin to 350 kelvin raises diffusivity from 1e-15 to 5e-15 square metres per second”. The reviewed quantities are diffusivity scale = 1 meter ** 2 / second; activation energy = 1 electron_volt; temperature before = 300 kelvin; temperature after = 350 kelvin; diffusivity before = 1e-15 meter ** 2 / second; diffusivity after = 5e-15 meter ** 2 / second.",
            "prefix": "ference = 1 meter ** 2 / second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: For p"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 3262,
            "end": 3804,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a positive activation energy of 1 electron volt and an unchanged Arrhenius mechanism, raising temperature from 300 kelvin to 350 kelvin raises diffusivity from 1e-15 to 5e-15 square metres per second”. The reviewed quantities are diffusivity scale = 1 meter ** 2 / second; activation energy = 1 electron_volt; temperature before = 300 kelvin; temperature after = 350 kelvin; diffusivity before = 1e-15 meter ** 2 / second; diffusivity after = 5e-15 meter ** 2 / second.",
            "prefix": "ference = 1 meter ** 2 / second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: For p"
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 3819,
            "end": 4242,
            "exact": "In equivalent wording, the document states: For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient. The diffusivity scale is recorded as 1 meter ** 2 / second. The bound Arrhenius operands are activation energy 1 electron volt, temperatures 300 and 350 kelvin, and diffusivities 1e-15 and 5e-15 square meter per second.",
            "prefix": "d; diffusivity after = 5e-15 meter ** 2 / second.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAfter the diffusion mechanism changed, "
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
          "document_ref": "qualification-fixture:materials:004",
          "document_digest": "sha256:18b3726822bd38027804cc5617389be11a5dd9c895e7ded4af2ccba86160204b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 4267,
            "end": 4505,
            "exact": "After the diffusion mechanism changed, temperature rose from 300 kelvin to 350 kelvin and the measured diffusion coefficient increased from 1e-15 meter ** 2 / second to 5e-15 meter ** 2 / second; the activation energy was 1 electron volt.",
            "prefix": "e-15 and 5e-15 square meter per second.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
