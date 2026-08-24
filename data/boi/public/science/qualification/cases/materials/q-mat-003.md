---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-MAT-003 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:materials:003",
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
      "ref": "sci-rule:materials:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:materials:003",
    "standard_id": "Q-MAT-003",
    "rule_id": "sci-rule:materials:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:materials:003:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:clear_violation",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 334,
            "exact": "A metastable phase with an available transformation pathway must remain indefinitely without approaching equilibrium. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA supercooled or superheated metastable"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "remains_indefinitely",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:in_scope_consistency",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 359,
            "end": 553,
            "exact": "A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "mperature is recorded as 298.15 kelvin.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the metastable"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:missing_required_condition",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 584,
            "end": 839,
            "exact": "Without specifying the metastable state, the report asserts: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "ure is recorded as 298.15 kelvin.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nWhen no transformation pathway is av"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:outside_validity_domain",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 867,
            "end": 1126,
            "exact": "When no transformation pathway is available, the report asserts: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "rature is recorded as 298.15 kelvin.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named supercooled spec"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "outside_phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:empirical_verification_required",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1162,
            "end": 1450,
            "exact": "For a named supercooled specimen, the report asserts: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. This named result requires measurement. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "s recorded as 298.15 kelvin.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "requested_phase_transformation_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:negation",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1463,
            "end": 1717,
            "exact": "Under the stated scientific conditions, it is not true that a supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "e context temperature is recorded as 298.15 kelvin.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA supercooled or superheated metastable phase"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:unit_variation",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1736,
            "end": 1980,
            "exact": "A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The reviewed quantities are context temperature = 25 °C; context temperature reference = 298.15 kelvin.",
            "prefix": "ext temperature is recorded as 298.15 kelvin.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": 25,
                "unit": "°C"
              },
              {
                "quantity_kind": "context_temperature_reference",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "context_temperature",
            "value": "298.15",
            "unit": "kelvin"
          },
          {
            "quantity_kind": "context_temperature",
            "value": 25,
            "unit": "°C"
          }
        ]
      },
      {
        "case_id": "sci-case:materials:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2012,
            "end": 2284,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available”. The reviewed quantity is context temperature = 298.15 kelvin.",
            "prefix": "ature reference = 298.15 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: A sup"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
              "ambiguity:sci-rule:materials:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:materials:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2012,
            "end": 2284,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available”. The reviewed quantity is context temperature = 298.15 kelvin.",
            "prefix": "ature reference = 298.15 kelvin.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: A sup"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "remains_indefinitely",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
              "ambiguity:sci-rule:materials:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:materials:003:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:paraphrase",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2299,
            "end": 2537,
            "exact": "In equivalent wording, the document states: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": " quantity is context temperature = 298.15 kelvin.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA metastable phase with a kinetically b"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "transforms_toward",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "available"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      },
      {
        "case_id": "sci-case:materials:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:materials:003",
        "evaluation_rule_id": "sci-rule:materials:003",
        "claim_packet": {
          "claim_id": "claim:materials:003:false_red_prevention",
          "document_ref": "qualification-fixture:materials:003",
          "document_digest": "sha256:d6919ebaeff82da78558b77d8f43d251134852a3cf32da6f08080e278aa74cdc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2562,
            "end": 2725,
            "exact": "A metastable phase with a kinetically blocked pathway is reported to persist during the observation interval. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "mperature is recorded as 298.15 kelvin.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:metastable-phase",
            "relation_kind": "causal_relation",
            "predicate": "remains_indefinitely",
            "object_concept_id": "sci:concept:equilibrium-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "context_temperature",
                "value": "298.15",
                "unit": "kelvin"
              }
            ],
            "conditions": [
              {
                "condition_id": "metastable_state",
                "value": "supercooled_or_superheated"
              },
              {
                "condition_id": "transformation_pathway",
                "value": "kinetically_blocked"
              },
              {
                "condition_id": "process_context",
                "value": "phase_transformation"
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
        "rationale": "This natural-language claim exercises metastable phases can transform through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:phase-transformation"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-MAT-003

Ten public natural-claim fixtures qualify only `sci-rule:materials:003`. No operational authority is created.
