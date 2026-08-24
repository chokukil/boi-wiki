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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:92f5c2d6baf953c895ddea6d3e6bebe63b54fb4aeb36634facfdd82c81bf6b3c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 137,
            "exact": "At equilibrium the reaction quotient Q is 2 while the equilibrium constant K is 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:475dad32a4aa383ccd06f6979aa248b2fc58a8b280e1decf5e4b773357e7181c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 140,
            "exact": "At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:5a5540d2c349065aab6a5ef4745c30a459aa16a1e2c572292deebb15c1af89ca",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 204,
            "exact": "The report omits a required scientific condition while stating: At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:c7b8df3d469e138247ab213732f0c0152a62433212d63eaef894279025b984e3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 204,
            "exact": "Before the reaction has reached equilibrium, the report states: At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:a8c56316c60dd5f35d675a0c6418da17c39c76da9f76527f0dcdc8e0a1e18f68",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 228,
            "exact": "For a named reacting mixture, the report states: At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4; the named result requires measurement. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:1d025db5ffaf485ccd7e39b8a45661d28479cfd1643200209b612276a4365c59",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 183,
            "exact": "The report denies the equality even though at equilibrium the reaction quotient q is 4 and the equilibrium constant k is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:2789e42ed82a5407110e78fc2eaac2df7b7969ea286094221039420a0d440b0b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 148,
            "exact": "At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4. The concentration scale is recorded as 1000 mole / meter ** 3.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:16cddb1e5af49b2a8aecefa3519cd6ed9a6cfc5c3f188326dbe23485654adddb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 304,
            "exact": "A blurred table entry can be read as either 'At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4' or 'At equilibrium the reaction quotient Q is 2 while the equilibrium constant K is 4', so the equation is unresolved. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:16cddb1e5af49b2a8aecefa3519cd6ed9a6cfc5c3f188326dbe23485654adddb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 304,
            "exact": "A blurred table entry can be read as either 'At equilibrium the reaction quotient Q is 4 and the equilibrium constant K is also 4' or 'At equilibrium the reaction quotient Q is 2 while the equilibrium constant K is 4', so the equation is unresolved. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:70bd8fe9c455fd989ae6cbb2888fb0ff12e8e9de5039dd4af647d94fca6a45a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 166,
            "exact": "Using equivalent wording, at equilibrium the reaction quotient q is 4 and the equilibrium constant k is also 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:chemistry:004",
          "document_digest": "sha256:17a98a5613f998b2a7b9bad506a8b8f4d9371c41384b0c8faad8a9bd2b2bb2d0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 221,
            "exact": "When the activity basis is outside this rule's required scope, the document states: At equilibrium the reaction quotient Q is 2 while the equilibrium constant K is 4. The concentration scale is recorded as 1 mole / liter.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_specified_standard_state"
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
