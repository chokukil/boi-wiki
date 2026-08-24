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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 166,
            "end": 310,
            "exact": "A dry-film spin model may ignore solvent evaporation and still claim unlimited validity. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA dry-film spin model records solvent e"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 335,
            "end": 488,
            "exact": "A dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "osity is recorded as 1 pascal * second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 519,
            "end": 741,
            "exact": "Without one required scientific condition, the document asserts that a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "is recorded as 1 pascal * second.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a nonvolatile ideal liquid outsi"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 769,
            "end": 1019,
            "exact": "For a nonvolatile ideal liquid outside the stated dry-photoresist use, the document asserts that a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "ty is recorded as 1 pascal * second.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named volatile resist "
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1055,
            "end": 1324,
            "exact": "For a named volatile resist and exhaust condition, the document asserts that a dry-film spin model records solvent evaporation, drying termination, and its validation domain; the named result requires measurement. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "corded as 1 pascal * second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a dry-film spin model records s"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1337,
            "end": 1510,
            "exact": "It is not true that a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "dynamic viscosity is recorded as 1 pascal * second.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA dry-film spin model records solvent evapora"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1529,
            "end": 1750,
            "exact": "A dry-film spin model records solvent evaporation, drying termination, and its validation domain. The reviewed quantities are dynamic viscosity = 1000 millipascal * second; dynamic viscosity reference = 1 pascal * second.",
            "prefix": "c viscosity is recorded as 1 pascal * second.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1782,
            "end": 2013,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A dry-film spin model records solvent evaporation, drying termination, and its validation domain”. The reviewed quantity is dynamic viscosity = 1 pascal * second.",
            "prefix": "y reference = 1 pascal * second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a dry-film spin model reco"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1782,
            "end": 2013,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A dry-film spin model records solvent evaporation, drying termination, and its validation domain”. The reviewed quantity is dynamic viscosity = 1 pascal * second.",
            "prefix": "y reference = 1 pascal * second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a dry-film spin model reco"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2028,
            "end": 2204,
            "exact": "In equivalent wording, a dry-film spin model records solvent evaporation, drying termination, and its validation domain. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "uantity is dynamic viscosity = 1 pascal * second.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nWith no validation-domain record, the e"
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
          "document_ref": "qualification-fixture:spin-coating:003",
          "document_digest": "sha256:01050109128bf320e5bf1954dc55c6926443be840c02f4b4c479446c7b82adec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2229,
            "end": 2398,
            "exact": "With no validation-domain record, the evaporation-aware model is not asserted to apply to the named dry-film use. The dynamic viscosity is recorded as 1 pascal * second.",
            "prefix": "osity is recorded as 1 pascal * second.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
