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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:47b1153a3f6b09897bfacc4eca989865cdf730e728375ff34f35d221dcff98fe",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "Wet, post-spin, and post-bake film thicknesses are interchangeable without a measurement state or uncertainty. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:5b1a052859c764e3abb4029265b31085aa9f0f845bf0c575d5c8df1c09b3516f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 165,
            "exact": "A photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:f8f23cecbdacae054bf939b74b75c47f10beb6f5a4c5c4e049e0bef7f789fa31",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 234,
            "exact": "Without one required scientific condition, the document asserts that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:400d7f0e1ac8093abaacc55f849fc5d4877e52b8168731c65341c268f6ec11df",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "For a non-photoresist coating method, the document asserts that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:975b4123ed36625269df517878830971c58e855f55b8efe4ae40cf65302469a1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 284,
            "exact": "For a named photo track and thickness metrology tool, the document asserts that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:7a5b632223e45c1bb8fb81ca064110820be72632e013bfaa1831678b333aed58",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 185,
            "exact": "It is not true that a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:62406fedc72d3a27dd331f49566aabfb34ed841135da2bc4df1771a7c8fac3f6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 170,
            "exact": "A photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 0.001 micrometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:2647be8c306458de79bbe1624d47af3c001bf4f5e787c8ede05e275fb8e1a334",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "The document calls the proposition 'Spin-film measurement state' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:2647be8c306458de79bbe1624d47af3c001bf4f5e787c8ede05e275fb8e1a334",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "The document calls the proposition 'Spin-film measurement state' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:c0a030fc916e37e5ae15823726e80305cb0032a02979292d261becbd86b3f709",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "In equivalent wording, a photoresist film-thickness result identifies its measurement state and uncertainty before states are compared. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:001",
          "document_digest": "sha256:d0e869ce7ed75e507fcf0910b95b9c038c716e369c1d5c1c530f05c07d0138f9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 192,
            "exact": "When the process method is outside this rule's required scope, the document denies that film thickness result applies to measurement state. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_spin_coating"
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
