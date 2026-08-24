---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-004 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:004",
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
      "ref": "sci-rule:common:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:004",
    "standard_id": "Q-COM-004",
    "rule_id": "sci-rule:common:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:004:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:clear-violation",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-clear-violation",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 37,
            "exact": "Foundation topic 004 clear-violation.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "negative",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Exercises clear_violation for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      },
      {
        "case_id": "sci-case:common:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:in-scope-consistency",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-in-scope-consistency",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 42,
            "exact": "Foundation topic 004 in-scope-consistency.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Exercises in_scope_consistency for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      },
      {
        "case_id": "sci-case:common:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:missing-required-condition",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-missing-required-condition",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 48,
            "exact": "Foundation topic 004 missing-required-condition.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Exercises missing_required_condition for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      },
      {
        "case_id": "sci-case:common:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:outside-validity-domain",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-outside-validity-domain",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 45,
            "exact": "Foundation topic 004 outside-validity-domain.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "__outside__"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Exercises outside_validity_domain for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      },
      {
        "case_id": "sci-case:common:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:008",
        "claim_packet": {
          "claim_id": "claim:common:004:empirical-verification-required",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-empirical-verification-required",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 53,
            "exact": "Foundation topic 004 empirical-verification-required.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:model",
            "relation_kind": "empirical_relation",
            "predicate": "valid_for_use",
            "object_concept_id": "sci:concept:intended-use",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "validation_domain_documented",
                "value": true
              },
              {
                "condition_id": "model_basis",
                "value": "theoretical"
              },
              {
                "condition_id": "intended_use_within_recorded_domain",
                "value": true
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:model"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "A topic-specific application claim is routed to the Foundation model-validation rule and stops for empirical evidence.",
        "expected_evidence_path": [
          "sci-evidence:common:model-validity"
        ]
      },
      {
        "case_id": "sci-case:common:004:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:negation",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-negation",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 30,
            "exact": "Foundation topic 004 negation.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "negative",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Exercises negation for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      },
      {
        "case_id": "sci-case:common:004:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:unit-variation",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-unit-variation",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 36,
            "exact": "Foundation topic 004 unit-variation.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "unit_probe",
                "value": 100,
                "unit": "cm"
              }
            ],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Exercises unit_variation for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "unit_probe",
            "value": 1,
            "unit": "m"
          },
          {
            "quantity_kind": "unit_probe",
            "value": 100,
            "unit": "cm"
          }
        ]
      },
      {
        "case_id": "sci-case:common:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:decision-changing-ambiguity",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-decision-changing-ambiguity",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 49,
            "exact": "Foundation topic 004 decision-changing-ambiguity.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [
              "ambiguity:common:004"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Two permitted interpretations produce different candidate verdicts, so interpretation must stop at the ambiguity gate.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:004:decision-changing-alternative",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-decision-changing-alternative",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 51,
            "exact": "Foundation topic 004 decision-changing-alternative.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "negative",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [
              "ambiguity:common:004"
            ],
            "user_confirmed": false
          }
        }
      },
      {
        "case_id": "sci-case:common:004:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:paraphrase",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-paraphrase",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 32,
            "exact": "Foundation topic 004 paraphrase.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:measurement-result",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Exercises paraphrase for SCI-COM-004.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      },
      {
        "case_id": "sci-case:common:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:004",
        "claim_packet": {
          "claim_id": "claim:common:004:false-red-prevention",
          "document_ref": "qualification:common:004",
          "document_digest": "sha256:task2-004-false-red-prevention",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 42,
            "exact": "Foundation topic 004 false-red-prevention.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:unsupported:4",
            "relation_kind": "empirical_relation",
            "predicate": "context_defined",
            "object_concept_id": "sci:concept:measurand",
            "polarity": "positive",
            "quantities": [],
            "conditions": [
              {
                "condition_id": "measurand_defined",
                "value": true
              },
              {
                "condition_id": "measurement_conditions_defined",
                "value": true
              },
              {
                "condition_id": "measurement_procedure_scope",
                "value": "documented"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "A neighboring unsupported concept must remain nondecisive instead of producing a red violation.",
        "expected_evidence_path": [
          "sci-evidence:common:measurand-result"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-COM-004

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
