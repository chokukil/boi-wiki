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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 299,
            "exact": "Vacancies, dislocation lines, and grain boundaries are the same dimensional defect. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nVacancies, dislocation lines, and grain"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 324,
            "end": 474,
            "exact": "Vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 505,
            "end": 724,
            "exact": "Without one required scientific condition, the document asserts that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "scale is recorded as 1 nanometer.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor an amorphous structure with no i"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 752,
            "end": 990,
            "exact": "For an amorphous structure with no identified grain boundary, the document asserts that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ss scale is recorded as 1 nanometer.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named microscopy speci"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1026,
            "end": 1274,
            "exact": "For a named microscopy specimen, the document asserts that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": " is recorded as 1 nanometer.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that vacancies, dislocation lines, a"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1287,
            "end": 1457,
            "exact": "It is not true that vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "he film thickness scale is recorded as 1 nanometer.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nVacancies, dislocation lines, and grain bound"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1476,
            "end": 1688,
            "exact": "Vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The reviewed quantities are film thickness scale = 0.001 micrometer; film thickness scale reference = 1 nanometer.",
            "prefix": "m thickness scale is recorded as 1 nanometer.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1720,
            "end": 1948,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, vacancies, dislocation lin"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1720,
            "end": 1948,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, vacancies, dislocation lin"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1963,
            "end": 2136,
            "exact": "In equivalent wording, vacancies, dislocation lines, and grain boundaries occupy distinct defect-dimensionality classes. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "d quantity is film thickness scale = 1 nanometer.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA surface step is not classified here a"
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
          "document_ref": "qualification-fixture:materials:001",
          "document_digest": "sha256:f2854cede5a261ed164bef4b786e312e18df532f46e86572c4529082753c7e32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2161,
            "end": 2302,
            "exact": "A surface step is not classified here as a vacancy, dislocation line, or grain boundary. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
