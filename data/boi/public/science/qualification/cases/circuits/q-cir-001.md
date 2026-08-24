---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CIR-001 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:circuits:001",
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
      "ref": "sci-rule:circuits:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:circuits:001",
    "standard_id": "Q-CIR-001",
    "rule_id": "sci-rule:circuits:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:circuits:001:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:clear_violation",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 162,
            "end": 311,
            "exact": "The algebraic current sum at the identified lumped-circuit node is 1 ampere but is asserted to equal zero. The current scale is recorded as 1 ampere.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe algebraic current sum at the identi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:in_scope_consistency",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 336,
            "end": 456,
            "exact": "The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": " current scale is recorded as 1 ampere.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report omits a required scien"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:missing_required_condition",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 487,
            "end": 671,
            "exact": "The report omits a required scientific condition while stating: The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "nt scale is recorded as 1 ampere.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nAt a distributed node where stored c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:outside_validity_domain",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 699,
            "end": 893,
            "exact": "At a distributed node where stored charge is changing, the report states: The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "rrent scale is recorded as 1 ampere.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named instrumented cir"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "outside_kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:empirical_verification_required",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 929,
            "end": 1146,
            "exact": "For a named instrumented circuit node, the report states: The algebraic current sum at the identified lumped-circuit node is 0 amperes; the named result requires measurement. The current scale is recorded as 1 ampere.",
            "prefix": "ale is recorded as 1 ampere.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nThe report denies the equality even though the alge"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "requested_node_current_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:negation",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1159,
            "end": 1322,
            "exact": "The report denies the equality even though the algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "urement. The current scale is recorded as 1 ampere.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe algebraic current sum at the identified l"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:unit_variation",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1341,
            "end": 1516,
            "exact": "The algebraic current sum at the identified lumped-circuit node is 0 amperes. The reviewed quantities are current scale = 1000 milliampere; current scale reference = 1 ampere.",
            "prefix": "s. The current scale is recorded as 1 ampere.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1000,
                "unit": "milliampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "current_scale_reference",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
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
        "case_id": "sci-case:circuits:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1548,
            "end": 1808,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The algebraic current sum at the identified lumped-circuit node is 0 amperes”. The reviewed quantities are current scale = 1 ampere; algebraic current sum = 0 ampere; zero current = 0 ampere.",
            "prefix": "rent scale reference = 1 ampere.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, the algebraic current s"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
              "ambiguity:sci-rule:circuits:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:circuits:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1548,
            "end": 1808,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The algebraic current sum at the identified lumped-circuit node is 0 amperes”. The reviewed quantities are current scale = 1 ampere; algebraic current sum = 0 ampere; zero current = 0 ampere.",
            "prefix": "rent scale reference = 1 ampere.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, the algebraic current s"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
              "ambiguity:sci-rule:circuits:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:circuits:001:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:paraphrase",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1823,
            "end": 1969,
            "exact": "Using equivalent wording, the algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": " current sum = 0 ampere; zero current = 0 ampere.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nCurrents taken from multiple circuit no"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 0,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "bound_node_reference"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      },
      {
        "case_id": "sci-case:circuits:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:circuits:001",
        "evaluation_rule_id": "sci-rule:circuits:001",
        "claim_packet": {
          "claim_id": "claim:circuits:001:false_red_prevention",
          "document_ref": "qualification-fixture:circuits:001",
          "document_digest": "sha256:bcee467e521f2d57c154b066e6015392876c62d22669f2824186925c27111bd6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1994,
            "end": 2143,
            "exact": "Currents taken from multiple circuit nodes cannot be combined as the algebraic sum at one identified node. The current scale is recorded as 1 ampere.",
            "prefix": " current scale is recorded as 1 ampere.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:node-current-sum",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:zero-current",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "algebraic_current_sum",
                "value": 1,
                "unit": "ampere"
              },
              {
                "quantity_kind": "zero_current",
                "value": 0,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "current_reference_convention",
                "value": "consistent"
              },
              {
                "condition_id": "circuit_model",
                "value": "lumped_matter"
              },
              {
                "condition_id": "node_charge_accumulation",
                "value": "none"
              },
              {
                "condition_id": "node_identity",
                "value": "multiple_nodes"
              },
              {
                "condition_id": "balance_context",
                "value": "kcl_node_sum"
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
        "rationale": "This natural-language claim exercises kirchhoff current law through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:kcl-law"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CIR-001

Ten public natural-claim fixtures qualify only `sci-rule:circuits:001`. No operational authority is created.
