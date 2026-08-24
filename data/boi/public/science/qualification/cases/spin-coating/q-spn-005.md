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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:0a93bb2cfd937419049654ffc7e55068750172c6d184312adbfa91746faa0d4e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 132,
            "exact": "A general spin mechanism alone proves the exact film thickness on every coater. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:677d860f4f596baf135fe85f1a6d6a50943aa16aa88b6226b8b5fa0fa746ca40",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "An exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:d101dc2617b10e7345bcb78c1c230576bacdea578c19a2622ffba845bed2f21a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "Without one required scientific condition, the document asserts that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:d18d3d3e3dd47e3c07fd91b81b8d0857051f4728b7c800a3d34da1122def4d2a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 262,
            "exact": "For a purely qualitative mechanism claim with no equipment-specific result, the document asserts that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:a039d263e0cf86161ac91c7a90c63fc5b0b4f29d9351a62cfd1c0966332c7200",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 279,
            "exact": "For a named production coater and metrology sequence, the document asserts that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:42d5b3f464de03cbc3684080aa82f3857c6ed522ce4d3e7504d70acd3336dbc2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 180,
            "exact": "It is not true that an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:ef19d6be4c052e5d6ebd2caa124b089a8735d1845f426bd28c2d641059998812",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 165,
            "exact": "An exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 0.001 micrometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:9b410151a0f25f0e0b15026d19501720cb98527a924dc84ed4b6a85e98f34cea",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 210,
            "exact": "The document calls the proposition 'Equipment-specific thickness requires measurement' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:9b410151a0f25f0e0b15026d19501720cb98527a924dc84ed4b6a85e98f34cea",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 210,
            "exact": "The document calls the proposition 'Equipment-specific thickness requires measurement' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:3897efff0447ae7226aeb72d8a9900e9012486d9bbeabec15a6204ae8d0fb8fc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 183,
            "exact": "In equivalent wording, an exact equipment-specific spin result requires qualified measurement inside a recorded validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:005",
          "document_digest": "sha256:0fd0d733a2c98d4665f856e646e9aa0cd90faf4893e9fe7ed44fcf87ff5e8c2a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 215,
            "exact": "When the thinning continues until is outside this rule's required scope, the document denies that equipment specific spin result applies to qualified observation. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_drying_stops_flow"
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
