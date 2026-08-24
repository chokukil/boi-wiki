---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-007 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:007",
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
      "ref": "sci-rule:common:007"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:007",
    "standard_id": "Q-COM-007",
    "rule_id": "sci-rule:common:007",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:007:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:clear_violation",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 328,
            "exact": "A reproducibility condition excludes changes in location, operator, measuring system, and replicate measurement. The reviewed quantity is location separation = 1 meter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA reproducibility condition includes di"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:in_scope_consistency",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 353,
            "end": 524,
            "exact": "A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The reviewed quantity is location separation = 1 meter.",
            "prefix": "ntity is location separation = 1 meter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying changed condit"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:missing_required_condition",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 555,
            "end": 791,
            "exact": "Without specifying changed condition set, the report states that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The reviewed quantity is location separation = 1 meter.",
            "prefix": "is location separation = 1 meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:outside_validity_domain",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 819,
            "end": 1061,
            "exact": "In a different scientific context, the report nevertheless states that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The reviewed quantity is location separation = 1 meter.",
            "prefix": "ty is location separation = 1 meter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:empirical_verification_required",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1097,
            "end": 1352,
            "exact": "For a named realization, the report asserts that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. No qualified observation is bound. The reviewed quantity is location separation = 1 meter.",
            "prefix": "cation separation = 1 meter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a reproducibility condition inc"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              },
              {
                "condition_id": "requested_foundation_007_qualified_observation",
                "value": "unqualified_observation"
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
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:negation",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1365,
            "end": 1556,
            "exact": "It is not true that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The reviewed quantity is location separation = 1 meter.",
            "prefix": "reviewed quantity is location separation = 1 meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA reproducibility condition includes differen"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:unit_variation",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1575,
            "end": 1797,
            "exact": "A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The reviewed quantities are location separation = 100 centimeter; location separation reference = 1 meter.",
            "prefix": "ed quantity is location separation = 1 meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "location_separation_reference",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "location_separation",
            "value": 1,
            "unit": "meter"
          },
          {
            "quantity_kind": "location_separation",
            "value": 100,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1829,
            "end": 2070,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements”. The reviewed quantity is location separation = 1 meter.",
            "prefix": " separation reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [
              "ambiguity:common:007"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:007:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1829,
            "end": 2070,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements”. The reviewed quantity is location separation = 1 meter.",
            "prefix": " separation reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [
              "ambiguity:common:007"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:007",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:007:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:paraphrase",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2085,
            "end": 2304,
            "exact": "In equivalent wording, the document states that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The reviewed quantity is location separation = 1 meter.",
            "prefix": "viewed quantity is location separation = 1 meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nMeasurements repeated under the same co"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "locations_operators_systems_and_replicates"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      },
      {
        "case_id": "sci-case:common:007:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:007",
        "claim_packet": {
          "claim_id": "claim:common:007:false_red_prevention",
          "document_ref": "qualification-fixture:common:007",
          "document_digest": "sha256:e7853e5e6d30fdeee88af5a213ba37e7cab8e6cf3485cbc20813482f5a7a127f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2329,
            "end": 2508,
            "exact": "Measurements repeated under the same conditions do not instantiate the varied conditions in the reproducibility definition. The reviewed quantity is location separation = 1 meter.",
            "prefix": "ntity is location separation = 1 meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:reproducibility-condition",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:varied-measurement-conditions",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "location_separation",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "changed_condition_set",
                "value": "same_conditions"
              },
              {
                "condition_id": "definition_context",
                "value": "vim_reproducibility_condition"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:precision"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:repeatability-reproducibility"
        ],
        "matrix_rule_id": "sci-rule:common:007"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-007

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
