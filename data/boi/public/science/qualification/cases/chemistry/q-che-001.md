---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CHE-001 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:chemistry:001",
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
      "ref": "sci-rule:chemistry:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:chemistry:001",
    "standard_id": "Q-CHE-001",
    "rule_id": "sci-rule:chemistry:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:chemistry:001:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:clear_violation",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:e7184cbe1a9e4889bd8c8a85b262b6d8750671552fde3afec7cbc71e1fb2b6e1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 134,
            "exact": "Two moles of solute in one litre of solution are reported as 3 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 3,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:in_scope_consistency",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:4ce12a183e15c41179f24a22b56a39afffeb249ce4b6e63bd584dd28159a5259",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 134,
            "exact": "Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:missing_required_condition",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:e3f231427f116246d64eb24868c61156c77f97c136cd19a4caaedd932f4f5a65",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 198,
            "exact": "The report omits a required scientific condition while stating: Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              }
            ],
            "conditions": [
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:outside_validity_domain",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:5d6358243227025ee0a2da451d9785c6b9299cbeedebbec7c4fe85efceb281b6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 213,
            "exact": "Under a mass-concentration convention rather than molarity, the report states: Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "outside_molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:empirical_verification_required",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:ec11e2f7bce53540fdb612889f6addc5a32ea081b94b1f4b13f97b840e6caffa",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 232,
            "exact": "For a named solution preparation batch, the report states: Two moles of solute in one litre of solution are reported as 2 moles per litre; the named result requires measurement. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:negation",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:11d50189324d276c8fc7f00ec53bcf544c8920e3f3cc08e574a1b0009c5be81e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 177,
            "exact": "The report denies the equality even though two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:unit_variation",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:9a549b8c809bd99ce87ab05637804adb67510235ad08d3ab2a4a5f0e487e9480",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 142,
            "exact": "Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1000 mole / meter ** 3.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1000,
                "unit": "mole / meter ** 3"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "concentration_scale",
            "value": 1,
            "unit": "mole / liter"
          },
          {
            "quantity_kind": "concentration_scale",
            "value": 1000,
            "unit": "mole / meter ** 3"
          }
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:decision_changing_ambiguity",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:ad3029801be0b14f195d372e58235c04255f66fb8a62cb2a338b9d0a55801b59",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 295,
            "exact": "A blurred table entry can be read as either 'Two moles of solute in one litre of solution are reported as 2 moles per litre' or 'Two moles of solute in one litre of solution are reported as 3 moles per litre', so the equation is unresolved. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:chemistry:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:chemistry:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:ad3029801be0b14f195d372e58235c04255f66fb8a62cb2a338b9d0a55801b59",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 295,
            "exact": "A blurred table entry can be read as either 'Two moles of solute in one litre of solution are reported as 2 moles per litre' or 'Two moles of solute in one litre of solution are reported as 3 moles per litre', so the equation is unresolved. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 3,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:chemistry:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:chemistry:001:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:paraphrase",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:1ff9b0a93ac13d6c1ea8ec9f0caae0e92b52d7302446135db5e8105e45f6508e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "Using equivalent wording, two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 2,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      },
      {
        "case_id": "sci-case:chemistry:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:chemistry:001",
        "evaluation_rule_id": "sci-rule:chemistry:001",
        "claim_packet": {
          "claim_id": "claim:chemistry:001:false_red_prevention",
          "document_ref": "qualification:chemistry:001",
          "document_digest": "sha256:d22ab1f29ba66d1893b4a8c9d59a453bca97fe6d14cddccf739bebbcbfe99ed1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 223,
            "exact": "When the solute amount basis is outside this rule's required scope, the document states: Two moles of solute in one litre of solution are reported as 3 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:molar-concentration",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:amount-per-solution-volume",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "molar_concentration",
                "value": 3,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "solute_amount",
                "value": 2,
                "unit": "mole"
              },
              {
                "quantity_kind": "solution_volume",
                "value": 1,
                "unit": "liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "solute_amount_basis",
                "value": "outside_moles_of_named_solute"
              },
              {
                "condition_id": "concentration_convention",
                "value": "molarity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises molar concentration definition through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:amount-concentration"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CHE-001

Ten public natural-claim fixtures qualify only `sci-rule:chemistry:001`. No operational authority is created.
