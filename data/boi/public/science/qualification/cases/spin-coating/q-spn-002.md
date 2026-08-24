---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:002",
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
      "ref": "sci-rule:spin-coating:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:002",
    "standard_id": "Q-SPN-002",
    "rule_id": "sci-rule:spin-coating:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:clear_violation",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:3aa4e33824f1af69b574cbd9382998ecf34604c8bc84317c76a35be1a3583454",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 149,
            "exact": "The Emslie-style model is universally valid without recorded assumptions or a validation domain. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:in_scope_consistency",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:b4d526230301118b6568940aee2d65796b69061b033e09a2831d5ae07f6714bd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 159,
            "exact": "The Emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:missing_required_condition",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:8a73417329e0c924d1d3b5fc701fe872b82fbee950572f91e4b76e61a7f728ff",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 228,
            "exact": "Without one required scientific condition, the document asserts that the emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:outside_validity_domain",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:7ea8ac71bdd5661d0a5776935407d4185509d9c625723cd83391edcdec0dedb5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 246,
            "exact": "For an intended use outside the recorded ideal-model domain, the document asserts that the emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "outside_inside_recorded_domain"
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
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:empirical_verification_required",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:7ba6d153e1fd7b91896a35605bd8d9dc99dfc83bfe5e89818ad8a1248999740e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 285,
            "exact": "For a named resist and coater compared with the ideal model, the document asserts that the emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated; the named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:negation",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:b9fd3e4987e4e1fa6248e9139c0a566e128852ea5e83de0c1126a54d7443d90e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 179,
            "exact": "It is not true that the Emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:unit_variation",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:884fef78c2101f5ce216e59d1b3f035e20ad87dbade0551dc200a01d3b967563",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 164,
            "exact": "The Emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated. The film thickness scale is recorded as 0.001 micrometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
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
        "case_id": "sci-case:spin-coating:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:decision_changing_ambiguity",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:96836368be091558b1f0bc312442b7a58d1f4b22b8afaae93978e0508345a891",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 197,
            "exact": "The document calls the proposition 'Emslie-style ideal-model assumptions' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:96836368be091558b1f0bc312442b7a58d1f4b22b8afaae93978e0508345a891",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 197,
            "exact": "The document calls the proposition 'Emslie-style ideal-model assumptions' valid without resolving whether it affirms or denies that proposition. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:paraphrase",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:17146d301f33d5d9fd6d9dd7afbec3f30d05ace82c7fa5df2f579ee4521ad9b4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 182,
            "exact": "In equivalent wording, the emslie-style model is used only inside a recorded validation domain with its ideal assumptions stated. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:002",
        "evaluation_rule_id": "sci-rule:spin-coating:002",
        "claim_packet": {
          "claim_id": "claim:spin-coating:002:false_red_prevention",
          "document_ref": "qualification:spin-coating:002",
          "document_digest": "sha256:01a6d4ea0462691b8d683d045baf8bbdedda0515461d1bc982ea3d1f3db8405c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 196,
            "exact": "When the validation domain ref is outside this rule's required scope, the document denies that emslie style spin model applies to intended use. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:emslie-style-spin-model",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intended-use",
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
                "condition_id": "model_assumption_set",
                "value": "bound_assumption_record"
              },
              {
                "condition_id": "validation_domain_ref",
                "value": "outside_bound_science_knowledge"
              },
              {
                "condition_id": "intended_use",
                "value": "inside_recorded_domain"
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
        "rationale": "This natural-language claim exercises emslie-style ideal-model assumptions through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SPN-002

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:002`. No operational authority is created.
