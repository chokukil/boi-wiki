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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:097dc4caa417b437a6204549660f9556e5a9238660e7dbd79132d52f0b406150",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 157,
            "exact": "A reproducibility condition excludes changes in location, operator, measuring system, and replicate measurement. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:ab53be608913ad111d4c478239d0dc39fe12b592ffec9589c67f95dbe4f212fb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:5fe16cab7672f4984fa4391fcef06a97da4dda0249f8490c32f43121a963739a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 225,
            "exact": "Without specifying changed condition set, the report states that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:6024a239b370c262d48ac959c30d72cc669149644d00c79d0eb62afc69e67d3a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 231,
            "exact": "In a different scientific context, the report nevertheless states that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:f254d0b43ca1f8a9605caf6567610f400e88d0848db7d03e062f858bf97949d5",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 244,
            "exact": "For a named realization, the report asserts that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:8002cc2221749843cae9a04a9510e4ca890ce168db7ba3d8ae6bd99aa81853d7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 180,
            "exact": "It is not true that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:7332e81200b921119af525556afa9aa8d4df39262b48f74f63e29d89b8edf040",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 186,
            "exact": "A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The same location separation is written as 100 centimeter and 1 meter.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:780553cd7f9016d9129ad8e87105129829b7fcd6bc5920216a315cc9721fb0b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 327,
            "exact": "The wording leaves unresolved whether 'A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements.' or instead 'A reproducibility condition excludes changes in location, operator, measuring system, and replicate measurement.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:780553cd7f9016d9129ad8e87105129829b7fcd6bc5920216a315cc9721fb0b3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 327,
            "exact": "The wording leaves unresolved whether 'A reproducibility condition includes different locations, operators, measuring systems, and replicate measurements.' or instead 'A reproducibility condition excludes changes in location, operator, measuring system, and replicate measurement.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:0c59ad669f1cf08f7d6b746b79ed791848890c0c4b3eea0dfcbc6dfa569c7c2a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 208,
            "exact": "In equivalent wording, the document states that a reproducibility condition includes different locations, operators, measuring systems, and replicate measurements. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:007",
          "document_digest": "sha256:044bee9b72025cc156fdcfd6931514b0b2b12de485ecc35aefb49d01ae03618e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 168,
            "exact": "Measurements repeated under the same conditions do not instantiate the varied conditions in the reproducibility definition. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
