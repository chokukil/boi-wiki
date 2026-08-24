---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-003 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:003",
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
      "ref": "sci-rule:spin-coating:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:003",
    "standard_id": "Q-SPN-003",
    "rule_id": "sci-rule:spin-coating:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:003:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:clear_violation",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:b37ed3306343d675f0e1fb3133e53af2524ff51cd311eb25aa265ffe4e0f696b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 144,
            "exact": "A dry-film spin model may ignore solvent evaporation and still claim unlimited validity. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:in_scope_consistency",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:5f3ec7df993dbd75df3c8914351768d7791c07bceab7de57de20ad8c5221354d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 153,
            "exact": "A dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:missing_required_condition",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:133ee40208a71f052874fee19ba5690058fafbe4096722b8f925c61a92796f5d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 222,
            "exact": "Without one required scientific condition, the document asserts that a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:outside_validity_domain",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:64e06aca9305ebbec9ef45cde9f02e6361e1a566f97477708625f66dae499f7c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 250,
            "exact": "For a nonvolatile ideal liquid outside the stated dry-photoresist use, the document asserts that a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "outside_drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:empirical_verification_required",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:69d87dcc6a5df220b6dd7bec67a2be35c277691eb0c8359f681f0abb651f8f0a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 269,
            "exact": "For a named volatile resist and exhaust condition, the document asserts that a dry-film spin model records solvent evaporation, drying termination, and its validation domain; the named result requires measurement. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "requested_evaporation_model_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:negation",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:8379cb4f69889f1f03b741c30d54bb371cc2dce442a1af23e212ea852cef3adb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 173,
            "exact": "It is not true that a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:unit_variation",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:42df778ef0153d70ed879a91fabcee3fd579263c6973dc7492a6a424dac7225d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 224,
            "exact": "A dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1000 millipascal * second. The same dynamic viscosity is referenced as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
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
        "case_id": "sci-case:spin-coating:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:decision_changing_ambiguity",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:c43f39ab6dc698634c83499fc3e6909e1804ff2d6a3675c1a4300d9424ff68c1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 199,
            "exact": "The document calls the proposition 'Evaporation-aware spin-model limits' valid without resolving whether it affirms or denies that proposition. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:c43f39ab6dc698634c83499fc3e6909e1804ff2d6a3675c1a4300d9424ff68c1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 199,
            "exact": "The document calls the proposition 'Evaporation-aware spin-model limits' valid without resolving whether it affirms or denies that proposition. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:003:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:paraphrase",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:04abcb5ad8e149c75e8f704506fde425db2a797f74141c9526806add6788a49f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 176,
            "exact": "In equivalent wording, a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:003",
        "evaluation_rule_id": "sci-rule:spin-coating:003",
        "claim_packet": {
          "claim_id": "claim:spin-coating:003:false_red_prevention",
          "document_ref": "qualification:spin-coating:003",
          "document_digest": "sha256:9653f2f7eaf4109a5f0665be403a8af62067c092d5da596b4d844e49f03d748b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 169,
            "exact": "With no validation-domain record, the evaporation-aware model is not asserted to apply to the named dry-film use. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:evaporation-aware-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:dry-film-thickness",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "solvent_evaporation_model",
                "value": "explicit_term"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "unavailable"
              },
              {
                "condition_id": "thinning_termination",
                "value": "drying_relevant"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises evaporation-aware spin-model limits through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-spin-mechanism"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SPN-003

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:003`. No operational authority is created.
