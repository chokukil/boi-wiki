---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-MAT-001 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:materials:001",
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
      "ref": "sci-rule:materials:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:materials:001",
    "standard_id": "Q-MAT-001",
    "rule_id": "sci-rule:materials:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:materials:001:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:clear_violation",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:f02ecacc02b7d3d8eae16e1e4a6487c5203fd9a7d0672290108f2d4fb0d818ca",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 136,
            "exact": "Vacancies, dislocation lines, and grain boundaries are the same dimensional defect. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:in_scope_consistency",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:c7de2fec592df9cce5fb83e206d3dee54f4b7628580e92827abe0c5333102446",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 150,
            "exact": "Vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:missing_required_condition",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:181466807e12d106991b901e6e91f2f1eb3643b7f4b1e65ddf264dcda1d18727",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 219,
            "exact": "Without one required scientific condition, the document asserts that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:outside_validity_domain",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:cc6b124554c8412c5bbd8e048f3aa5e86dce17f6ca804af86c72a9dd6d09af66",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 238,
            "exact": "For an amorphous structure with no identified grain boundary, the document asserts that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "outside_crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:empirical_verification_required",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:28b30e07e5ddd9aaf90458536bdfea0fbf069f64d29d68c101c85af7c666776b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 248,
            "exact": "For a named microscopy specimen, the document asserts that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "requested_defect_classification_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:negation",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:2bfb18643b049045f014a83bb1a809932597c9526f9cf70fee8be3bbc7d9e05c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 170,
            "exact": "It is not true that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:unit_variation",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:5f638470a4ec04228d8f63d7b380278181f207fd4e343d7a64fb93ff6ecdd007",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 215,
            "exact": "Vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 0.001 micrometer. The same film thickness scale is referenced as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
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
        "case_id": "sci-case:materials:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:decision_changing_ambiguity",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:27195f26ab6ddcb7a4cd873e5948fd98060c569b81365a5b02752520a570658c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 194,
            "exact": "The document calls the proposition 'Defect dimensional classification' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
              "ambiguity:sci-rule:materials:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:materials:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:27195f26ab6ddcb7a4cd873e5948fd98060c569b81365a5b02752520a570658c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 194,
            "exact": "The document calls the proposition 'Defect dimensional classification' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
              "ambiguity:sci-rule:materials:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:materials:001:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:paraphrase",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:365145a0ce065c65e587f44fc1468314e8c0f4072d81ad0dffc1289f9949faa7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 173,
            "exact": "In equivalent wording, vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "vacancy_dislocation_or_grain_boundary"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      },
      {
        "case_id": "sci-case:materials:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:materials:001",
        "evaluation_rule_id": "sci-rule:materials:001",
        "claim_packet": {
          "claim_id": "claim:materials:001:false_red_prevention",
          "document_ref": "qualification:materials:001",
          "document_digest": "sha256:a54b8664b596d2847d4559c71894d9d13aaa3f7c1efbbe44dc61228d0dfa9985",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 141,
            "exact": "A surface step is not classified here as a vacancy, dislocation line, or grain boundary. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:crystal-defect",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:defect-dimensionality",
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
                "condition_id": "defect_type",
                "value": "surface_step"
              },
              {
                "condition_id": "material_structure",
                "value": "crystalline"
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
        "rationale": "This natural-language claim exercises defect dimensional classification through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:structure-grain"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-MAT-001

Ten public natural-claim fixtures qualify only `sci-rule:materials:001`. No operational authority is created.
