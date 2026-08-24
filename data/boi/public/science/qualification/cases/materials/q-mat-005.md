---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-MAT-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:materials:005",
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
      "ref": "sci-rule:materials:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:materials:005",
    "standard_id": "Q-MAT-005",
    "rule_id": "sci-rule:materials:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:materials:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:clear_violation",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:4e948b0ca78aba85e9f42915ce4a9b6531f757686bd1cbc619901a5356598f2c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 174,
            "exact": "For the same chemical composition, a bulk mechanical property is automatically equal to the deposited thin-film property. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "automatically_equal",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:in_scope_consistency",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:3e4cbc2fbd7c78f14af8d9b2ed2b1587112cbd33f651ee362ad43e9dd0e6fb4c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 214,
            "exact": "Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:missing_required_condition",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:fddb64f56042e8a87c84ba8dc500b8b4803b1e7b7caae2578bf3c867749ab64a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 273,
            "exact": "Without specifying the property class, the report asserts: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:outside_validity_domain",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:c4089e5bc75e3546dbf70a9624846d7e09f0f332eaba2fe66591b5de3574e5e1",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 293,
            "exact": "For a nonmechanical property not covered by this evidence, the report asserts: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "outside_deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:empirical_verification_required",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:91fcee860ca33d0b23831c37f7d6b21ddb742e9e2edbd74681c4f59e14219838",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 318,
            "exact": "For a named deposited film and bulk coupon, the report asserts: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. This named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "requested_thin_film_property_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:negation",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:d70595a190678cc0155efc48b07afc6be70a8528251ea4604e346f2fe6271dff",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 274,
            "exact": "Under the stated scientific conditions, it is not true that even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:unit_variation",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:fe499b33d0750c953c8e721f177950557e632778b37bd3f745213f20997facc7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 279,
            "exact": "Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 0.001 micrometer. The same film thickness scale is referenced as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
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
        "case_id": "sci-case:materials:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:decision_changing_ambiguity",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:8f713c8d360f77192019daec06dd1bb814664e4e85d8860c860fc78911f4a0ff",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 389,
            "exact": "The wording leaves unresolved whether 'Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior.' or instead 'For the same chemical composition, a bulk mechanical property is automatically equal to the deposited thin-film property'. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
              "ambiguity:sci-rule:materials:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:materials:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:8f713c8d360f77192019daec06dd1bb814664e4e85d8860c860fc78911f4a0ff",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 389,
            "exact": "The wording leaves unresolved whether 'Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior.' or instead 'For the same chemical composition, a bulk mechanical property is automatically equal to the deposited thin-film property'. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "automatically_equal",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
              "ambiguity:sci-rule:materials:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:materials:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:paraphrase",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:45328971908acaaa1b9f1510ff746c9fe1532ab5b6d588d2d26ea0d5b0fdf5cf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 258,
            "exact": "In equivalent wording, the document states: Even at the same chemical composition, a thin film's mechanical properties need not equal bulk properties because deposition conditions can change film behavior. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "not_automatically_transferable",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "same"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      },
      {
        "case_id": "sci-case:materials:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:materials:005",
        "evaluation_rule_id": "sci-rule:materials:005",
        "claim_packet": {
          "claim_id": "claim:materials:005:false_red_prevention",
          "document_ref": "qualification:materials:005",
          "document_digest": "sha256:e7fd4292ac1854d9cb77ce13473c551d0a7d39f140288a1b0f951197efc55e09",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 167,
            "exact": "A bulk specimen and deposited thin film of different composition are reported to have equal mechanical properties. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:bulk-property-transfer",
            "relation_kind": "causal_relation",
            "predicate": "automatically_equal",
            "object_concept_id": "sci:concept:thin-film-property",
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
                "condition_id": "property_class",
                "value": "mechanical"
              },
              {
                "condition_id": "material_form",
                "value": "thin_film"
              },
              {
                "condition_id": "comparison_composition",
                "value": "different"
              },
              {
                "condition_id": "film_origin",
                "value": "deposition_defined"
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
        "rationale": "This natural-language claim exercises bulk properties do not automatically transfer to thin films through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:materials:nist-thin-film-bulk-difference"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-MAT-005

Ten public natural-claim fixtures qualify only `sci-rule:materials:005`. No operational authority is created.
