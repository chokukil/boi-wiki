---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-CIR-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:circuits:005",
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
      "ref": "sci-rule:circuits:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:circuits:005",
    "standard_id": "Q-CIR-005",
    "rule_id": "sci-rule:circuits:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:circuits:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:clear_violation",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 162,
            "end": 310,
            "exact": "A capacitor's state variable is always inductor current and an inductor's is always capacitor voltage. The capacitance scale is recorded as 1 farad.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe capacitor voltage and inductor curr"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:in_scope_consistency",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 335,
            "end": 474,
            "exact": "The capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "pacitance scale is recorded as 1 farad.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:missing_required_condition",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 505,
            "end": 713,
            "exact": "Without one required scientific condition, the document asserts that the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "nce scale is recorded as 1 farad.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor an unidentified distributed elec"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:outside_validity_domain",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 741,
            "end": 965,
            "exact": "For an unidentified distributed electromagnetic structure, the document asserts that the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "itance scale is recorded as 1 farad.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named storage componen"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "outside_lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:empirical_verification_required",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1001,
            "end": 1247,
            "exact": "For a named storage component under test, the document asserts that the capacitor voltage and inductor current are their respective lumped-model state variables; the named result requires measurement. The capacitance scale is recorded as 1 farad.",
            "prefix": "cale is recorded as 1 farad.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that the capacitor voltage and induc"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "requested_storage_state_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:negation",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1260,
            "end": 1419,
            "exact": "It is not true that the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "ment. The capacitance scale is recorded as 1 farad.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe capacitor voltage and inductor current ar"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:unit_variation",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1438,
            "end": 1635,
            "exact": "The capacitor voltage and inductor current are their respective lumped-model state variables. The reviewed quantities are capacitance scale = 1000 millifarad; capacitance scale reference = 1 farad.",
            "prefix": "The capacitance scale is recorded as 1 farad.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1000,
                "unit": "millifarad"
              },
              {
                "quantity_kind": "capacitance_scale_reference",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "capacitance_scale",
            "value": 1,
            "unit": "farad"
          },
          {
            "quantity_kind": "capacitance_scale",
            "value": 1000,
            "unit": "millifarad"
          }
        ]
      },
      {
        "case_id": "sci-case:circuits:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1667,
            "end": 1884,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The capacitor voltage and inductor current are their respective lumped-model state variables”. The reviewed quantity is capacitance scale = 1 farad.",
            "prefix": "tance scale reference = 1 farad.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the capacitor voltage and "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:circuits:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:circuits:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1667,
            "end": 1884,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The capacitor voltage and inductor current are their respective lumped-model state variables”. The reviewed quantity is capacitance scale = 1 farad.",
            "prefix": "tance scale reference = 1 farad.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the capacitor voltage and "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:circuits:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:circuits:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:paraphrase",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1899,
            "end": 2061,
            "exact": "In equivalent wording, the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "reviewed quantity is capacitance scale = 1 farad.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA resistor is not a capacitor or induct"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "capacitor_or_inductor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      },
      {
        "case_id": "sci-case:circuits:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:circuits:005",
        "evaluation_rule_id": "sci-rule:circuits:005",
        "claim_packet": {
          "claim_id": "claim:circuits:005:false_red_prevention",
          "document_ref": "qualification-fixture:circuits:005",
          "document_digest": "sha256:98033d34bb0116a2b3c3e3dfd49dd5373dfaa4bee99c423bb110017edbade9af",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2086,
            "end": 2235,
            "exact": "A resistor is not a capacitor or inductor whose state variable is covered by this storage-element rule. The capacitance scale is recorded as 1 farad.",
            "prefix": "pacitance scale is recorded as 1 farad.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:energy-storage-element",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-variable",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "capacitance_scale",
                "value": 1,
                "unit": "farad"
              }
            ],
            "conditions": [
              {
                "condition_id": "element_type",
                "value": "resistor"
              },
              {
                "condition_id": "device_model",
                "value": "lumped_storage_element"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:resistance",
              "sci:binding:domain:electric-power"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises capacitor and inductor state variables through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:circuits:capacitor-inductor"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-CIR-005

Ten public natural-claim fixtures qualify only `sci-rule:circuits:005`. No operational authority is created.
