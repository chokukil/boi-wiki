---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-MAT-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:materials:002",
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
      "ref": "sci-rule:materials:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:materials:002",
    "standard_id": "Q-MAT-002",
    "rule_id": "sci-rule:materials:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:materials:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:clear_violation",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:7eb7047a72bef44fd54b84b563d6769ab70652cc6507d36126c064229013c3bf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 101,
            "exact": "Every defect cluster necessarily strengthens every metal. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:in_scope_consistency",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:4ed98cf98d1b5e325036d338925a3c36ea57b2a0aa77d629d9d11b6199c3d791",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 144,
            "exact": "The strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:missing_required_condition",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:208b0c51afc166d82fc5601a155b31fdfb8e6ce36b269656eaa4e4078da110ee",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 213,
            "exact": "Without one required scientific condition, the document asserts that the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:outside_validity_domain",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:5578c15468cee100a28163c21e25d0458d5f80f201d7d64af1b053ae827f72d9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 240,
            "exact": "For a quantitative alloy prediction beyond the cited defect examples, the document asserts that the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "outside_qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:empirical_verification_required",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:1e95d9a0471cab423f4aec24db5fce1a7097f7c8cf9a1bfe612104854bcaaab0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 253,
            "exact": "For a named alloy and heat-treatment batch, the document asserts that the strength effect depends on the identified defect-cluster type in the cited qualitative examples; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:negation",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:f27cba8112e7abb14f850f82a6f02932dfb8f27deb2eacc7289161d0d0a69b64",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 164,
            "exact": "It is not true that the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:unit_variation",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:f6fc670c610561b5f39163d85e4b8b2fdbf6f8deeba3994e639754863c7eef52",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 152,
            "exact": "The strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1000 millipascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1000,
                "unit": "millipascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "pressure_scale",
            "value": 1,
            "unit": "pascal"
          },
          {
            "quantity_kind": "pressure_scale",
            "value": 1000,
            "unit": "millipascal"
          }
        ]
      },
      {
        "case_id": "sci-case:materials:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:decision_changing_ambiguity",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:523261bfc1bae17654cfe22e6357dd2b0291ecceb7b5d7aa3ae441e6a460e7f9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 201,
            "exact": "The document calls the proposition 'Defect clusters have conditional strength effects' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
              "ambiguity:sci-rule:materials:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:materials:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:523261bfc1bae17654cfe22e6357dd2b0291ecceb7b5d7aa3ae441e6a460e7f9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 201,
            "exact": "The document calls the proposition 'Defect clusters have conditional strength effects' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
              "ambiguity:sci-rule:materials:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:materials:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:paraphrase",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:f16dacad0d424d58f6750549d290387771b1e7ced4c949504aa0e39299e72413",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 167,
            "exact": "In equivalent wording, the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      },
      {
        "case_id": "sci-case:materials:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:materials:002",
        "evaluation_rule_id": "sci-rule:materials:002",
        "claim_packet": {
          "claim_id": "claim:materials:002:false_red_prevention",
          "document_ref": "qualification:materials:002",
          "document_digest": "sha256:665d4f4bc1f8194764fb72f66dff01e182af9357052d8e86426b438aaa9d005e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 183,
            "exact": "When the defect cluster type is outside this rule's required scope, the document denies that defect cluster applies to mechanical strength. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:defect-cluster",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:mechanical-strength",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "effect_scope",
                "value": "cited_defect_types_qualitative"
              },
              {
                "condition_id": "defect_cluster_type",
                "value": "outside_void_or_precipitate"
              },
              {
                "condition_id": "claim_resolution",
                "value": "qualitative_strength_direction"
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
        "rationale": "This natural-language claim exercises defect clusters have conditional strength effects through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:defects-microstructure"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-MAT-002

Ten public natural-claim fixtures qualify only `sci-rule:materials:002`. No operational authority is created.
