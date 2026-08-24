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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 309,
            "exact": "Vapor pressure does not measure the molecular escaping tendency of the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nVapor pressure measures the escaping te"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 334,
            "end": 477,
            "exact": "Vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 508,
            "end": 720,
            "exact": "Without one required scientific condition, the document asserts that vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "re scale is recorded as 1 pascal.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor an open process whose transport "
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 748,
            "end": 981,
            "exact": "For an open process whose transport conditions are unspecified, the document asserts that vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "ssure scale is recorded as 1 pascal.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named solvent and exha"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1017,
            "end": 1272,
            "exact": "For a named solvent and exhaust configuration, the document asserts that vapor pressure measures the escaping tendency of molecules from the identified condensed substance; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "ale is recorded as 1 pascal.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that vapor pressure measures the esc"
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
                "condition_id": "requested_vapor_pressure_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1285,
            "end": 1448,
            "exact": "It is not true that vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "rement. The pressure scale is recorded as 1 pascal.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nVapor pressure measures the escaping tendency"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1467,
            "end": 1666,
            "exact": "Vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The reviewed quantities are pressure scale = 1000 millipascal; pressure scale reference = 1 pascal.",
            "prefix": ". The pressure scale is recorded as 1 pascal.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "pressure_scale_reference",
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1698,
            "end": 1919,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Vapor pressure measures the escaping tendency of molecules from the identified condensed substance”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, vapor pressure measures th"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1698,
            "end": 1919,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Vapor pressure measures the escaping tendency of molecules from the identified condensed substance”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, vapor pressure measures th"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1934,
            "end": 2100,
            "exact": "In equivalent wording, vapor pressure measures the escaping tendency of molecules from the identified condensed substance. The pressure scale is recorded as 1 pascal.",
            "prefix": "e reviewed quantity is pressure scale = 1 pascal.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA gas-phase sample is not the named liq"
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
          "document_ref": "qualification-fixture:chemistry:003",
          "document_digest": "sha256:3ff4513a2e24727484c400044027c541e371248114d43963fc290033cfcc3e4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2125,
            "end": 2272,
            "exact": "A gas-phase sample is not the named liquid or solid to which this vapor-pressure definition is applied. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "gas_phase"
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
