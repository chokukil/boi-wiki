---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CHE-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:chemistry:004",
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
      "ref": "sci-rule:chemistry:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:chemistry:004",
    "standard_id": "Q-CHE-004",
    "rule_id": "sci-rule:chemistry:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:chemistry:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:clear_violation",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 300,
            "exact": "At equilibrium the reaction quotient Q is 2 while the equilibrium constant K is 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nAt equilibrium the reaction quotient Q "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 2,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:in_scope_consistency",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 325,
            "end": 465,
            "exact": "At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "on scale is recorded as 1 mole / liter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report omits a required scien"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:missing_required_condition",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 496,
            "end": 700,
            "exact": "The report omits a required scientific condition while stating: At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "le is recorded as 1 mole / liter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nBefore the reaction has reached equi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:outside_validity_domain",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 728,
            "end": 932,
            "exact": "Before the reaction has reached equilibrium, the report states: At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "scale is recorded as 1 mole / liter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named reacting mixture"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "outside_equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:empirical_verification_required",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 968,
            "end": 1196,
            "exact": "For a named reacting mixture, the report states: At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4; the named result requires measurement. The concentration scale is recorded as 1 mole / liter.",
            "prefix": " recorded as 1 mole / liter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nThe report denies the equality even though at equil"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "requested_equilibrium_composition_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:negation",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1209,
            "end": 1392,
            "exact": "The report denies the equality even though at equilibrium the reaction quotient q is 4 and the equilibrium constant k is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": " concentration scale is recorded as 1 mole / liter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nAt equilibrium the reaction quotient Q is 4 a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:unit_variation",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1411,
            "end": 1618,
            "exact": "At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The reviewed quantities are concentration scale = 1000 mole / meter ** 3; concentration scale reference = 1 mole / liter.",
            "prefix": "ntration scale is recorded as 1 mole / liter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1000,
                "unit": "mole / meter ** 3"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "concentration_scale_reference",
                "value": 1,
                "unit": "mole / liter"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
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
        "case_id": "sci-case:chemistry:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1650,
            "end": 1948,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4”. The reviewed quantities are concentration scale = 1 mole / liter; reaction quotient = 4 dimensionless; equilibrium constant = 4 dimensionless.",
            "prefix": "cale reference = 1 mole / liter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, at equilibrium the reac"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
              "ambiguity:sci-rule:chemistry:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:chemistry:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1650,
            "end": 1948,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4”. The reviewed quantities are concentration scale = 1 mole / liter; reaction quotient = 4 dimensionless; equilibrium constant = 4 dimensionless.",
            "prefix": "cale reference = 1 mole / liter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, at equilibrium the reac"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 2,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
              "ambiguity:sci-rule:chemistry:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:chemistry:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:paraphrase",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1963,
            "end": 2129,
            "exact": "Using equivalent wording, at equilibrium the reaction quotient q is 4 and the equilibrium constant k is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "sionless; equilibrium constant = 4 dimensionless.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nWith an unspecified concentration basis"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 4,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "specified_standard_state"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      },
      {
        "case_id": "sci-case:chemistry:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:chemistry:004",
        "evaluation_rule_id": "sci-rule:chemistry:004",
        "claim_packet": {
          "claim_id": "claim:chemistry:004:false_red_prevention",
          "document_ref": "qualification-fixture:chemistry:004",
          "document_digest": "sha256:327805c48840dbfd0edb181d897ae6efcc207ee13a436a525bcef50d3adb8c42",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2154,
            "end": 2334,
            "exact": "With an unspecified concentration basis, the reported reaction quotient and equilibrium constant are not directly comparable. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "on scale is recorded as 1 mole / liter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reaction-quotient",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:equilibrium-constant",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "concentration_scale",
                "value": 1,
                "unit": "mole / liter"
              },
              {
                "quantity_kind": "reaction_quotient",
                "value": 2,
                "unit": "dimensionless"
              },
              {
                "quantity_kind": "equilibrium_constant",
                "value": 4,
                "unit": "dimensionless"
              }
            ],
            "conditions": [
              {
                "condition_id": "balanced_reaction",
                "value": "stoichiometry_bound"
              },
              {
                "condition_id": "activity_basis",
                "value": "unspecified_concentration_basis"
              },
              {
                "condition_id": "reaction_state",
                "value": "equilibrium"
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
        "rationale": "This natural-language claim exercises reaction quotient at equilibrium through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:reaction-equilibrium"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CHE-004

Ten public natural-claim fixtures qualify only `sci-rule:chemistry:004`. No operational authority is created.
