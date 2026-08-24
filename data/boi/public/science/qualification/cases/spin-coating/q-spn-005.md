---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:005",
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
      "ref": "sci-rule:spin-coating:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:005",
    "standard_id": "Q-SPN-005",
    "rule_id": "sci-rule:spin-coating:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:clear_violation",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 166,
            "end": 298,
            "exact": "A general spin mechanism alone proves the exact film thickness on every coater. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nAn exact equipment-specific spin result"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:in_scope_consistency",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 323,
            "end": 483,
            "exact": "An exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:missing_required_condition",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 514,
            "end": 743,
            "exact": "Without one required scientific condition, the document asserts that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "scale is recorded as 1 nanometer.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a purely qualitative mechanism c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:outside_validity_domain",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 771,
            "end": 1033,
            "exact": "For a purely qualitative mechanism claim with no equipment-specific result, the document asserts that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ss scale is recorded as 1 nanometer.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named production coate"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "outside_qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:empirical_verification_required",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1069,
            "end": 1348,
            "exact": "For a named production coater and metrology sequence, the document asserts that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": " is recorded as 1 nanometer.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that an exact equipment-specific spi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "requested_coater_transfer_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:negation",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1361,
            "end": 1541,
            "exact": "It is not true that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "he film thickness scale is recorded as 1 nanometer.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nAn exact equipment-specific spin result requi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:unit_variation",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1560,
            "end": 1782,
            "exact": "An exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The reviewed quantities are film thickness scale = 0.001 micrometer; film thickness scale reference = 1 nanometer.",
            "prefix": "m thickness scale is recorded as 1 nanometer.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
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
        "case_id": "sci-case:spin-coating:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1814,
            "end": 2052,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “An exact equipment-specific spin result requires qualified measurement inside a recorded validation domain”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, an exact equipment-specifi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
              "ambiguity:sci-rule:spin-coating:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1814,
            "end": 2052,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “An exact equipment-specific spin result requires qualified measurement inside a recorded validation domain”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, an exact equipment-specifi"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
              "ambiguity:sci-rule:spin-coating:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:paraphrase",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2067,
            "end": 2250,
            "exact": "In equivalent wording, an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "d quantity is film thickness scale = 1 nanometer.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nWhen radial flow is interrupted before "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:005",
        "evaluation_rule_id": "sci-rule:spin-coating:005",
        "claim_packet": {
          "claim_id": "claim:spin-coating:005:false_red_prevention",
          "document_ref": "qualification-fixture:spin-coating:005",
          "document_digest": "sha256:7f4ce892e0de23f0e725d0f406afa818f77d38a0c029c57db44f7a2d87c38f36",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2275,
            "end": 2461,
            "exact": "When radial flow is interrupted before drying stops it, the equipment-specific result is not transferred by this drying-limited rule. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:equipment-specific-spin-result",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:qualified-observation",
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
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
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
                "condition_id": "thinning_continues_until",
                "value": "flow_interrupted_before_drying"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualification_requirement_only"
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
        "rationale": "This natural-language claim exercises equipment-specific thickness requires measurement through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity",
          "sci-evidence:spin-coating:microchemicals-equipment-influence"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SPN-005

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:005`. No operational authority is created.
