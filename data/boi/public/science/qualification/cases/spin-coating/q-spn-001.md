---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-001 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:001",
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
      "ref": "sci-rule:spin-coating:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:001",
    "standard_id": "Q-SPN-001",
    "rule_id": "sci-rule:spin-coating:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:001:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:clear_violation",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 166,
            "end": 329,
            "exact": "Wet, post-spin, and post-bake film thicknesses are interchangeable without a measurement state or uncertainty. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA photoresist film-thickness result ide"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:in_scope_consistency",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 354,
            "end": 519,
            "exact": "A photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:missing_required_condition",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 550,
            "end": 784,
            "exact": "Without one required scientific condition, the document asserts that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "scale is recorded as 1 nanometer.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a non-photoresist coating method"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:outside_validity_domain",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 812,
            "end": 1041,
            "exact": "For a non-photoresist coating method, the document asserts that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ss scale is recorded as 1 nanometer.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named photo track and "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "outside_film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:empirical_verification_required",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1077,
            "end": 1361,
            "exact": "For a named photo track and thickness metrology tool, the document asserts that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": " is recorded as 1 nanometer.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a photoresist film-thickness re"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "requested_film_state_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:negation",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1374,
            "end": 1559,
            "exact": "It is not true that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "he film thickness scale is recorded as 1 nanometer.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA photoresist film-thickness result identifie"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:unit_variation",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1578,
            "end": 1805,
            "exact": "A photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The reviewed quantities are film thickness scale = 0.001 micrometer; film thickness scale reference = 1 nanometer.",
            "prefix": "m thickness scale is recorded as 1 nanometer.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": "0.001",
                "unit": "micrometer"
              },
              {
                "quantity_kind": "film_thickness_scale_reference",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "film_thickness_scale",
            "value": 1,
            "unit": "nanometer"
          },
          {
            "quantity_kind": "film_thickness_scale",
            "value": "0.001",
            "unit": "micrometer"
          }
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1837,
            "end": 2080,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A photoresist film-thickness result identifies its measurement state and uncertainty before states are compared”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a photoresist film-thickne"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1837,
            "end": 2080,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A photoresist film-thickness result identifies its measurement state and uncertainty before states are compared”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a photoresist film-thickne"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:001:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:paraphrase",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2095,
            "end": 2283,
            "exact": "In equivalent wording, a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "d quantity is film thickness scale = 1 nanometer.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA slot-die coating result is not a spin"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:001",
        "evaluation_rule_id": "sci-rule:spin-coating:001",
        "claim_packet": {
          "claim_id": "claim:spin-coating:001:false_red_prevention",
          "document_ref": "qualification-fixture:spin-coating:001",
          "document_digest": "sha256:192a90f000b825bd4c9b639a96208fbb58195338e77d13098c2dd99634730f33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2308,
            "end": 2465,
            "exact": "A slot-die coating result is not a spin-coated film-thickness result covered by this process-state rule. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:film-thickness-result",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-state",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "uncertainty_record",
                "value": "value_unit_and_coverage_bound"
              },
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "slot_die_coating"
              },
              {
                "condition_id": "comparison_target",
                "value": "film_thickness_between_named_states"
              }
            ],
            "process_stage": null,
            "material_state": "dry_post_bake_or_explicit_state"
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
        "rationale": "This natural-language claim exercises spin-film measurement state through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result",
          "sci-evidence:spin-coating:microchemicals-film-state-change"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SPN-001

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:001`. No operational authority is created.
