---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:004",
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
      "ref": "sci-rule:spin-coating:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:004",
    "standard_id": "Q-SPN-004",
    "rule_id": "sci-rule:spin-coating:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:clear_violation",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:d54a165f75a26337250b3ed4fdfc861ae9e3a0a4d4672fce869c75a25b812ca2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 248,
            "exact": "During final coat spin, increasing spin speed while the bound photoresist, viscosity, solids, spin time, environment, and dry post-bake measurement state are held constant increases attainable dry film thickness. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:in_scope_consistency",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:e1ee650526f87217ea815f69af75eec6932fd1b73b71fe6505c36de048e9de73",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 223,
            "exact": "For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:missing_required_condition",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:4a4f20bd4144fa9730625c291edc3f41505c8e577b1cbe58ad56f3f47eb7d936",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 282,
            "exact": "Without specifying the product family, the report asserts: For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:outside_validity_domain",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:2dfbe53ef815f53d39a59210c67d12c3c791f6fd459c8a77b684e4edfc0a06f1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 302,
            "exact": "Outside the bound product revision or plotted speed range, the report asserts: For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "outside_inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:empirical_verification_required",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:8f8bc9bd1b05d1ed90cb940ea49502ac96f27d9f18c00f3a833476b82c79bdec",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 338,
            "exact": "For a named production coater using the bound product, the report asserts: For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. This named result requires measurement. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:negation",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:fe9cebb71f312de1408a4f40e500da77d5139bd17f2a9f5d742b03884b21c81b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 283,
            "exact": "Under the stated scientific conditions, it is not true that for final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:unit_variation",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:1e5b5fbb617c19aae3c0437f2a0371349eb65c44045082be34158f1cce83072a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 239,
            "exact": "For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. The spin rate is recorded as 1 revolution / minute.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "revolution / minute"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "spin_rate",
            "value": 1,
            "unit": "rpm"
          },
          {
            "quantity_kind": "spin_rate",
            "value": 1,
            "unit": "revolution / minute"
          }
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:decision_changing_ambiguity",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:c2aa071969a7cc3031b0a75799c414ac3e3f7f1acdeebd71de30e6023b436f31",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 489,
            "exact": "The wording leaves unresolved whether 'For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows.' or instead 'During final coat spin, increasing spin speed while the bound photoresist, viscosity, solids, spin time, environment, and dry post-bake measurement state are held constant increases attainable dry film thickness'. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:c2aa071969a7cc3031b0a75799c414ac3e3f7f1acdeebd71de30e6023b436f31",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 489,
            "exact": "The wording leaves unresolved whether 'For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows.' or instead 'During final coat spin, increasing spin speed while the bound photoresist, viscosity, solids, spin time, environment, and dry post-bake measurement state are held constant increases attainable dry film thickness'. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:paraphrase",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:cc9a0b98232b13fd74b3ad7b5cae56410c8acdefee0984453d42a29070028463",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 267,
            "exact": "In equivalent wording, the document states: For final coat spin under the bound resist, process, measurement-state, and plotted-range conditions, increasing spin speed decreases attainable film thickness; no numeric recipe follows. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:false_red_prevention",
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:5012f92b1c09461fbb5e639167aa0f0ce393db441e6e790228fb27cdc68961b5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 159,
            "exact": "When the process stage is outside this rule's required scope, the document states that spin speed increases film thickness. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "product_family",
                "value": "AZ 125nXT"
              },
              {
                "condition_id": "product_grade",
                "value": "AZ 125nXT-10 B"
              },
              {
                "condition_id": "source_revision",
                "value": "01/24"
              },
              {
                "condition_id": "spin_speed_rpm",
                "value": 1450.0,
                "unit": "rpm"
              },
              {
                "condition_id": "evidence_use_mode",
                "value": "plotted_markers_only"
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
                "condition_id": "resist_identity",
                "value": "same"
              },
              {
                "condition_id": "viscosity",
                "value": "same"
              },
              {
                "condition_id": "solids_fraction",
                "value": "same"
              },
              {
                "condition_id": "spin_time",
                "value": "same"
              },
              {
                "condition_id": "environment",
                "value": "same"
              },
              {
                "condition_id": "measurement_state",
                "value": "dry_post_bake"
              },
              {
                "condition_id": "comparison_domain",
                "value": "inside_bound_product_curve"
              }
            ],
            "process_stage": "outside_final_coat_spin",
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
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
          "sci-evidence:spin-coating:vendor-spin-curve-observation"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SPN-004

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:004`. No operational authority is created.
