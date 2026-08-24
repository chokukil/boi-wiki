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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:a57011986a39071a35e3828794e97a262e492b36f206005ba7526e8a954cffdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 149,
            "exact": "The algebraic current sum at the identified lumped-circuit node is 1 ampere but is asserted to equal zero. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:9b8c530988ecc8b443230ce66988832432ae0a185743d49fc64290e004b16580",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 120,
            "exact": "The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:449871b02af42cc2ed6745b962a604dd5944505a771526b5a21f89f7a25c7a43",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "The report omits a required scientific condition while stating: The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:5897e13109b0a5a42e12e17dc3abbb830ba8d0901a0b476082b87fd17dbc95dc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 194,
            "exact": "At a distributed node where stored charge is changing, the report states: The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:cfaeaf1cc77492b233892c1b7f97fd4a0eed599a89a1517ba17011a2f9af3c3f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 217,
            "exact": "For a named instrumented circuit node, the report states: The algebraic current sum at the identified lumped-circuit node is 0 amperes; the named result requires measurement. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:62d616b5ffabe9f23554be8ac7feadf8f6ad887c58a90146c9106abfd8652f72",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "The report denies the equality even though the algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:bd6d5979673fef1bf2f3095f421a6da82a96af0dee7472ad233e952a96af6a00",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 178,
            "exact": "The algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1000 milliampere. The same current scale is referenced as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:5e08fc6ab2e6f0a112545f7c99725f626fc69967639622f82289620ccfa57f6c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 308,
            "exact": "A blurred table entry can be read as either 'The algebraic current sum at the identified lumped-circuit node is 0 amperes' or 'The algebraic current sum at the identified lumped-circuit node is 1 ampere but is asserted to equal zero', so the equation is unresolved. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:5e08fc6ab2e6f0a112545f7c99725f626fc69967639622f82289620ccfa57f6c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 308,
            "exact": "A blurred table entry can be read as either 'The algebraic current sum at the identified lumped-circuit node is 0 amperes' or 'The algebraic current sum at the identified lumped-circuit node is 1 ampere but is asserted to equal zero', so the equation is unresolved. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:e0ab7ffd372c61a537ffda380c7dc34f2d3efb679a4f0c07cccec9f444737f67",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 146,
            "exact": "Using equivalent wording, the algebraic current sum at the identified lumped-circuit node is 0 amperes. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:001",
          "document_digest": "sha256:a9b196c82d3e1337c2ffbe011d0a02f098444664a1045aa39c3c49d81c5370a4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 149,
            "exact": "Currents taken from multiple circuit nodes cannot be combined as the algebraic sum at one identified node. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
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
