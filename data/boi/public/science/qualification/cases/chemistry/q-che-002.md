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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 163,
            "end": 306,
            "exact": "One thermodynamic phase may have arbitrarily nonuniform intensive properties throughout its volume. The pressure scale is recorded as 1 pascal.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA single thermodynamic phase has unifor"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 331,
            "end": 470,
            "exact": "A single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 501,
            "end": 709,
            "exact": "Without one required scientific condition, the document asserts that a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "re scale is recorded as 1 pascal.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a multiphase region with unresol"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 737,
            "end": 954,
            "exact": "For a multiphase region with unresolved interfaces, the document asserts that a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "ssure scale is recorded as 1 pascal.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named heterogeneous sp"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 990,
            "end": 1230,
            "exact": "For a named heterogeneous specimen, the document asserts that a single thermodynamic phase has uniform intensive properties throughout the identified region; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "ale is recorded as 1 pascal.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a single thermodynamic phase ha"
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
                "condition_id": "requested_phase_uniformity_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1243,
            "end": 1402,
            "exact": "It is not true that a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "rement. The pressure scale is recorded as 1 pascal.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA single thermodynamic phase has uniform inte"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1421,
            "end": 1616,
            "exact": "A single thermodynamic phase has uniform intensive properties throughout the identified region. The reviewed quantities are pressure scale = 1000 millipascal; pressure scale reference = 1 pascal.",
            "prefix": ". The pressure scale is recorded as 1 pascal.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "pressure_scale_reference",
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1648,
            "end": 1865,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A single thermodynamic phase has uniform intensive properties throughout the identified region”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a single thermodynamic pha"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1648,
            "end": 1865,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A single thermodynamic phase has uniform intensive properties throughout the identified region”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, a single thermodynamic pha"
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1880,
            "end": 2042,
            "exact": "In equivalent wording, a single thermodynamic phase has uniform intensive properties throughout the identified region. The pressure scale is recorded as 1 pascal.",
            "prefix": "e reviewed quantity is pressure scale = 1 pascal.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA temperature-gradient region spanning "
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
          "document_ref": "qualification-fixture:chemistry:002",
          "document_digest": "sha256:3db4b4fb456d991cc4a81ecdfa13b2ea20a827f77a3fb8bdb415c9f3c03d5748",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2067,
            "end": 2209,
            "exact": "A temperature-gradient region spanning multiple phases need not have uniform intensive properties. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "unbounded_gradient_region"
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
