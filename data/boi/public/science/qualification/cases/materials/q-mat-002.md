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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 264,
            "exact": "Every defect cluster necessarily strengthens every metal. The pressure scale is recorded as 1 pascal.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe strength effect depends on the iden"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 289,
            "end": 433,
            "exact": "The strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 464,
            "end": 677,
            "exact": "Without one required scientific condition, the document asserts that the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "re scale is recorded as 1 pascal.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a quantitative alloy prediction "
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 705,
            "end": 945,
            "exact": "For a quantitative alloy prediction beyond the cited defect examples, the document asserts that the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "ssure scale is recorded as 1 pascal.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named alloy and heat-t"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 981,
            "end": 1234,
            "exact": "For a named alloy and heat-treatment batch, the document asserts that the strength effect depends on the identified defect-cluster type in the cited qualitative examples; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "ale is recorded as 1 pascal.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that the strength effect depends on "
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
                "condition_id": "requested_defect_strength_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1247,
            "end": 1411,
            "exact": "It is not true that the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "rement. The pressure scale is recorded as 1 pascal.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe strength effect depends on the identified"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1430,
            "end": 1630,
            "exact": "The strength effect depends on the identified defect-cluster type in the cited qualitative examples. The reviewed quantities are pressure scale = 1000 millipascal; pressure scale reference = 1 pascal.",
            "prefix": ". The pressure scale is recorded as 1 pascal.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "pressure_scale_reference",
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1662,
            "end": 1884,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The strength effect depends on the identified defect-cluster type in the cited qualitative examples”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the strength effect depend"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1662,
            "end": 1884,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The strength effect depends on the identified defect-cluster type in the cited qualitative examples”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the strength effect depend"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1899,
            "end": 2066,
            "exact": "In equivalent wording, the strength effect depends on the identified defect-cluster type in the cited qualitative examples. The pressure scale is recorded as 1 pascal.",
            "prefix": "e reviewed quantity is pressure scale = 1 pascal.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAn isolated solute atom is not the void"
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
          "document_ref": "qualification-fixture:materials:002",
          "document_digest": "sha256:9ae7e819d33473684b193104727ba0dbb3efcd937026f53280f3e6d205ed7de8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2091,
            "end": 2230,
            "exact": "An isolated solute atom is not the void or precipitate cluster addressed by this strength rule. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "solute_atom"
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
