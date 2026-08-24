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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 297,
            "exact": "Two moles of solute in one litre of solution are reported as 3 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nTwo moles of solute in one litre of sol"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 322,
            "end": 456,
            "exact": "Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "on scale is recorded as 1 mole / liter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report omits a required scien"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 487,
            "end": 685,
            "exact": "The report omits a required scientific condition while stating: Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "le is recorded as 1 mole / liter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nUnder a mass-concentration conventio"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 713,
            "end": 926,
            "exact": "Under a mass-concentration convention rather than molarity, the report states: Two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "scale is recorded as 1 mole / liter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named solution prepara"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 962,
            "end": 1194,
            "exact": "For a named solution preparation batch, the report states: Two moles of solute in one litre of solution are reported as 2 moles per litre; the named result requires measurement. The concentration scale is recorded as 1 mole / liter.",
            "prefix": " recorded as 1 mole / liter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nThe report denies the equality even though two mole"
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
                "condition_id": "requested_solution_concentration_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1207,
            "end": 1384,
            "exact": "The report denies the equality even though two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": " concentration scale is recorded as 1 mole / liter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nTwo moles of solute in one litre of solution "
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1403,
            "end": 1604,
            "exact": "Two moles of solute in one litre of solution are reported as 2 moles per litre. The reviewed quantities are concentration scale = 1000 mole / meter ** 3; concentration scale reference = 1 mole / liter.",
            "prefix": "ntration scale is recorded as 1 mole / liter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "concentration_scale_reference",
                "value": 1,
                "unit": "mole / liter"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1636,
            "end": 1940,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Two moles of solute in one litre of solution are reported as 2 moles per litre”. The reviewed quantities are concentration scale = 1 mole / liter; molar concentration = 2 mole / liter; solute amount = 2 mole; solution volume = 1 liter.",
            "prefix": "cale reference = 1 mole / liter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, two moles of solute in "
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1636,
            "end": 1940,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Two moles of solute in one litre of solution are reported as 2 moles per litre”. The reviewed quantities are concentration scale = 1 mole / liter; molar concentration = 2 mole / liter; solute amount = 2 mole; solution volume = 1 liter.",
            "prefix": "cale reference = 1 mole / liter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, two moles of solute in "
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1955,
            "end": 2115,
            "exact": "Using equivalent wording, two moles of solute in one litre of solution are reported as 2 moles per litre. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "olute amount = 2 mole; solution volume = 1 liter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA mass concentration is not numerically"
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
          "document_ref": "qualification-fixture:chemistry:001",
          "document_digest": "sha256:3c6c454f47610cff518f7281867a03ff2eeb9dc01fad0d618f89b27777306f13",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2140,
            "end": 2297,
            "exact": "A mass concentration is not numerically equal to a molar concentration without molar-mass information. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "on scale is recorded as 1 mole / liter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "mass_of_named_solute"
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
