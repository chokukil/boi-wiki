---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CHE-003 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:chemistry:003",
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
      "ref": "sci-rule:chemistry:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:chemistry:003",
    "standard_id": "Q-CHE-003",
    "rule_id": "sci-rule:chemistry:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:chemistry:003:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:clear_violation",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:8e91d2a88948d4cf084e9b6ddbe7f5bb84eae66128f7aaa20cdcad1f49413f9c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 126,
            "exact": "Vapor pressure by itself fixes the evaporation rate of every open flowing process. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:in_scope_consistency",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:9264b97cce3446090bd68f4d8565499c06351940279d0a87e5ca8da279631ab3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 143,
            "exact": "Vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:missing_required_condition",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:d02de0f2ac48ebd6a74b995561dbbb5fb1b8bebd2c11c858bf29d785afd162f8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 212,
            "exact": "Without one required scientific condition, the document asserts that vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:outside_validity_domain",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:b2d64ebd4dd8f12d0cf40945213c08a01740250733c004e3034edde15337f65c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 233,
            "exact": "For an open process whose transport conditions are unspecified, the document asserts that vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "outside_escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:empirical_verification_required",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:a9d4802858f90255a23e192bf585a75fd8787d0c849f4544d9277c611a77f651",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 255,
            "exact": "For a named solvent and exhaust configuration, the document asserts that vapor pressure measures the escaping tendency of molecules from the identified condensed substance; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:negation",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:1b803e0b8b6b94b3d8d08b954d0abb7c790a735873359fcd955b08d21bea6286",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "It is not true that vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:unit_variation",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:36368a14e82eed16f560328928bd00efd86e3fd48239737998d9c7fd20d888c6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 151,
            "exact": "Vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1000 millipascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
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
        "case_id": "sci-case:chemistry:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:decision_changing_ambiguity",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:b567e03c46f9f3b8211940379411ba6d58399438a937923ac8fe76dafb58bdd2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "The document calls the proposition 'Vapor pressure and escaping tendency' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
              "ambiguity:sci-rule:chemistry:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:chemistry:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:b567e03c46f9f3b8211940379411ba6d58399438a937923ac8fe76dafb58bdd2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "The document calls the proposition 'Vapor pressure and escaping tendency' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
              "ambiguity:sci-rule:chemistry:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:chemistry:003:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:paraphrase",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:0e4e2f78be8a1d3ec5be98c862a03798538d9112a79cd594e7234526c72a6ded",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 166,
            "exact": "In equivalent wording, vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      },
      {
        "case_id": "sci-case:chemistry:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:chemistry:003",
        "evaluation_rule_id": "sci-rule:chemistry:003",
        "claim_packet": {
          "claim_id": "claim:chemistry:003:false_red_prevention",
          "document_ref": "qualification:chemistry:003",
          "document_digest": "sha256:afe2850dbec912985e715ba34c0f9a1b1d029a4980e5b22614fbded4ca4955e2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 191,
            "exact": "When the condensed substance is outside this rule's required scope, the document denies that vapor pressure applies to molecular escaping tendency. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:vapor-pressure",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:molecular-escaping-tendency",
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
                "condition_id": "condensed_substance",
                "value": "outside_named_liquid_or_solid"
              },
              {
                "condition_id": "claim_scope",
                "value": "escaping_tendency_only"
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
        "rationale": "This natural-language claim exercises vapor pressure and escaping tendency through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:chemistry:evaporation-vapor-pressure"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CHE-003

Ten public natural-claim fixtures qualify only `sci-rule:chemistry:003`. No operational authority is created.
