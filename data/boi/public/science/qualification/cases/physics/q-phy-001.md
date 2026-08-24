---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-PHY-001 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:physics:001",
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
      "ref": "sci-rule:physics:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:physics:001",
    "standard_id": "Q-PHY-001",
    "rule_id": "sci-rule:physics:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:physics:001:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:clear_violation",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 161,
            "end": 274,
            "exact": "Angular speed is merely an angular position with no time rate. The angular rate is recorded as 1 radian / second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nAngular speed is the magnitude of an an"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:in_scope_consistency",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 299,
            "end": 420,
            "exact": "Angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": " rate is recorded as 1 radian / second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:missing_required_condition",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 451,
            "end": 641,
            "exact": "Without one required scientific condition, the document asserts that angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "is recorded as 1 radian / second.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a non-rotational scalar record, "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:outside_validity_domain",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 669,
            "end": 852,
            "exact": "For a non-rotational scalar record, the document asserts that angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "te is recorded as 1 radian / second.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named encoder installa"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "outside_rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:empirical_verification_required",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 888,
            "end": 1108,
            "exact": "For a named encoder installation, the document asserts that angular speed is the magnitude of an angle's rate of change with time; the named result requires measurement. The angular rate is recorded as 1 radian / second.",
            "prefix": "corded as 1 radian / second.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that angular speed is the magnitude "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "requested_angular_speed_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:negation",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1121,
            "end": 1262,
            "exact": "It is not true that angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": " The angular rate is recorded as 1 radian / second.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nAngular speed is the magnitude of an angle's "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:unit_variation",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1281,
            "end": 1466,
            "exact": "Angular speed is the magnitude of an angle's rate of change with time. The reviewed quantities are angular rate = 0.001 radian / millisecond; angular rate reference = 1 radian / second.",
            "prefix": "ngular rate is recorded as 1 radian / second.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": "0.001",
                "unit": "radian / millisecond"
              },
              {
                "quantity_kind": "angular_rate_reference",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "angular_rate",
            "value": 1,
            "unit": "radian / second"
          },
          {
            "quantity_kind": "angular_rate",
            "value": "0.001",
            "unit": "radian / millisecond"
          }
        ]
      },
      {
        "case_id": "sci-case:physics:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1498,
            "end": 1697,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Angular speed is the magnitude of an angle's rate of change with time”. The reviewed quantity is angular rate = 1 radian / second.",
            "prefix": "e reference = 1 radian / second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, angular speed is the magni"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:physics:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:physics:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1498,
            "end": 1697,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Angular speed is the magnitude of an angle's rate of change with time”. The reviewed quantity is angular rate = 1 radian / second.",
            "prefix": "e reference = 1 radian / second.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, angular speed is the magni"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:physics:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:physics:001:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:paraphrase",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1712,
            "end": 1856,
            "exact": "In equivalent wording, angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "wed quantity is angular rate = 1 radian / second.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA linear-velocity quantity along a stra"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "angular_speed"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      },
      {
        "case_id": "sci-case:physics:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:physics:001",
        "evaluation_rule_id": "sci-rule:physics:001",
        "claim_packet": {
          "claim_id": "claim:physics:001:false_red_prevention",
          "document_ref": "qualification-fixture:physics:001",
          "document_digest": "sha256:5e55c6aa3c74556b998aa69c0773f9d6185850b402e5d5c7b8365513fcd592a9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1881,
            "end": 2016,
            "exact": "A linear-velocity quantity along a straight path is not an angular-speed angle rate. The angular rate is recorded as 1 radian / second.",
            "prefix": " rate is recorded as 1 radian / second.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:angular-speed",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:angle-rate",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "angular_rate",
                "value": 1,
                "unit": "radian / second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "linear_velocity"
              },
              {
                "condition_id": "motion_context",
                "value": "rotation_about_axis"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises angular speed is an angle rate through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:rotation-angular-speed"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-PHY-001

Ten public natural-claim fixtures qualify only `sci-rule:physics:001`. No operational authority is created.
