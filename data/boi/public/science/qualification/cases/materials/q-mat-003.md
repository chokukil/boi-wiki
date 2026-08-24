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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:82705ff02c8cfc04a6ee98362c0459d2a9fed16df30e32565fbb4d2766b72fe7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 171,
            "exact": "A metastable phase with an available transformation pathway must remain indefinitely without approaching equilibrium. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:0966d4224aa23019116da423cf6445a15616f456ddf86044cef4dc41ee44b69a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 194,
            "exact": "A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:84cd0feeb4fe1c76fc711f02357b21a5615a07db95da4042a51caee22dcad5bb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 255,
            "exact": "Without specifying the metastable state, the report asserts: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:947fa2da74cd181ac72a5305b014b239a7212c82cc008d6155868cf6f99d4185",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 259,
            "exact": "When no transformation pathway is available, the report asserts: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:ef4aad1c628562964923d7ca7b2ccf512a535908c3ec5309d35787329b160cb9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 288,
            "exact": "For a named supercooled specimen, the report asserts: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. This named result requires measurement. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:b2f5ba2b488d96fba4258a61b5e206e8774a8fd246d6f2d258d4abb5607ffd4d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 254,
            "exact": "Under the stated scientific conditions, it is not true that a supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:b60c0ece6761574fd3bb9157fe64fa8fb2cc3a9b7197612fa2aaef39f96803bd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 247,
            "exact": "A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 25 °C. The same context temperature is referenced as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:b02d168e2e0e72a1723ed6e2ac5d275e2126a89fac0677c97ab585972e9bc091",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 365,
            "exact": "The wording leaves unresolved whether 'A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available.' or instead 'A metastable phase with an available transformation pathway must remain indefinitely without approaching equilibrium'. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:b02d168e2e0e72a1723ed6e2ac5d275e2126a89fac0677c97ab585972e9bc091",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 365,
            "exact": "The wording leaves unresolved whether 'A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available.' or instead 'A metastable phase with an available transformation pathway must remain indefinitely without approaching equilibrium'. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:d78111b5abf1a55c308003a7f17895eed18e2c46bb0c54262fd5c8643fa512fb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 238,
            "exact": "In equivalent wording, the document states: A supercooled or superheated metastable phase can readily transform toward the equilibrium state when a transformation pathway is available. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:materials:003",
          "document_digest": "sha256:301eb3bbdfad0ac8d6473295834811d3d40562272ea52c172ea140e06b03e016",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "A metastable phase with a kinetically blocked pathway is reported to persist during the observation interval. The context temperature is recorded as 298.15 kelvin.",
            "prefix": "",
            "suffix": ""
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
