---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CHE-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:chemistry:002",
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
      "ref": "sci-rule:chemistry:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:chemistry:002",
    "standard_id": "Q-CHE-002",
    "rule_id": "sci-rule:chemistry:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:chemistry:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:clear_violation",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:a89e869a9e9829c3a96f443282951f0186560a9a23f0a018ccfcd834249f6cc0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 143,
            "exact": "One thermodynamic phase may have arbitrarily nonuniform intensive properties throughout its volume. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:in_scope_consistency",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:7733cbd2399704ef85d5041e6c5dfb1e95c408f098615f10a28a2c92163219db",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 139,
            "exact": "A single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:missing_required_condition",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:50f0dc57e54ad6230a1ed826131187924a3babe6983d559d908842c25e249c88",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 208,
            "exact": "Without one required scientific condition, the document asserts that a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:outside_validity_domain",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:c871b6714d68e59457736e26a80176ed227c4e6c7ad8b1575e190a457f62bb9c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 217,
            "exact": "For a multiphase region with unresolved interfaces, the document asserts that a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "outside_thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:empirical_verification_required",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:fd7358b19908503624c04697dd2f730a5372ddaa91566f325e53429a824f4424",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 240,
            "exact": "For a named heterogeneous specimen, the document asserts that a single thermodynamic phase has uniform intensive properties throughout the identified region; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:negation",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:51b7b9113d0a1e8c2cf93bf52cc1feab18e377f409c490d970d9f9eaeaf22472",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 159,
            "exact": "It is not true that a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:unit_variation",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:3ac693bdc2bebcfad956b5b75ebea63afdda5882eb11e0fdf19a1c3723298d9a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 147,
            "exact": "A single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1000 millipascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
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
        "case_id": "sci-case:chemistry:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:decision_changing_ambiguity",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:fece9d94380144f895fa305c328b7752529775eb5f89ec7a925355870147b1fb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "The document calls the proposition 'Phase has uniform intensive properties' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:chemistry:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:chemistry:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:fece9d94380144f895fa305c328b7752529775eb5f89ec7a925355870147b1fb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "The document calls the proposition 'Phase has uniform intensive properties' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:chemistry:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:chemistry:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:paraphrase",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:6a4005a8eae14b821b4d63d11d7ea5fb4a0c8ae16d43aa1058b759f0c636850e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 162,
            "exact": "In equivalent wording, a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      },
      {
        "case_id": "sci-case:chemistry:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:chemistry:002",
        "evaluation_rule_id": "sci-rule:chemistry:002",
        "claim_packet": {
          "claim_id": "claim:chemistry:002:false_red_prevention",
          "document_ref": "qualification:chemistry:002",
          "document_digest": "sha256:5c258bfb4ecc3d6c99c876140d2962e80b2e350789337744b187d86f65ad5985",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 186,
            "exact": "When the region of matter is outside this rule's required scope, the document denies that thermodynamic phase applies to intensive properties. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:thermodynamic-phase",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:intensive-properties",
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
                "condition_id": "region_of_matter",
                "value": "outside_explicit_bounded_region"
              },
              {
                "condition_id": "definition_context",
                "value": "thermodynamic_phase"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:catalyst",
              "sci:binding:domain:equilibrium-constant"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises phase has uniform intensive properties through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:substance-phase"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CHE-002

Ten public natural-claim fixtures qualify only `sci-rule:chemistry:002`. No operational authority is created.
