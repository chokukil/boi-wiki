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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:e1eb0ca879c84dca0b4d1999f9a6148c33b021bab0a1f02916edb2dec1e29b45",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 113,
            "exact": "Angular speed is merely an angular position with no time rate. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:4abe8fac4e583e0cd54d09ec32fb06bd1b98f76d922a47b42cf147e3c8141cbd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 121,
            "exact": "Angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:5a967cdc3c2bd9475e3bf4e52e17e37e8503c1c273ef52dcd042c5611cf9ceb9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 190,
            "exact": "Without one required scientific condition, the document asserts that angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:60a6514ce64e9e268567daf7bfe531a1eaf51b3ccdf59e67f91148c07501614c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 183,
            "exact": "For a non-rotational scalar record, the document asserts that angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:097ab83464c18c938e251091a962d2cba727dfedd2fd1b56bd0bf6f4048c542e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 220,
            "exact": "For a named encoder installation, the document asserts that angular speed is the magnitude of an angle's rate of change with time; the named result requires measurement. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:c08248dfc6f48efbd7bc0842dc523dcc580bfe6734342095d0c82f67e3c77941",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 141,
            "exact": "It is not true that angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:d4347822a049eb81946ab58a950142fe93dffa4bb63b99b04e608c7a825cfd50",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 130,
            "exact": "Angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 0.001 radian / millisecond.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:cd9f9b2ec4a5029fe0e2c2202c37146b4a98efcfdc0459e9e0adbd4da595d9a0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 189,
            "exact": "The document calls the proposition 'Angular speed is an angle rate' valid without resolving whether it affirms or denies that proposition. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:cd9f9b2ec4a5029fe0e2c2202c37146b4a98efcfdc0459e9e0adbd4da595d9a0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 189,
            "exact": "The document calls the proposition 'Angular speed is an angle rate' valid without resolving whether it affirms or denies that proposition. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:2bf14d7d08dd3db3a8ffe69d0bd6e354a605af08c33ee7b1049d80bb60aaad21",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 144,
            "exact": "In equivalent wording, angular speed is the magnitude of an angle's rate of change with time. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:001",
          "document_digest": "sha256:fa1fd0ca85de6dfeee705e666f79c1505811d9abde626e5dd0ada2260eafcf49",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 174,
            "exact": "When the quantity role is outside this rule's required scope, the document denies that angular speed applies to angle rate. The angular rate is recorded as 1 radian / second.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_angular_speed"
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
