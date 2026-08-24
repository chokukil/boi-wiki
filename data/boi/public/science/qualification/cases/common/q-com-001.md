---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-001 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:001",
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
      "ref": "sci-rule:common:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:001",
    "standard_id": "Q-COM-001",
    "rule_id": "sci-rule:common:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:001:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:clear_violation",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 301,
            "exact": "A sample length may be represented by a time unit without changing its scientific meaning. The reviewed quantity is sample length = 1 second.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA sample length is represented by a qua"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:in_scope_consistency",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 326,
            "end": 458,
            "exact": "A sample length is represented by a quantity whose unit has length dimensionality. The reviewed quantity is sample length = 1 meter.",
            "prefix": "d quantity is sample length = 1 second.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying quantity role,"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:missing_required_condition",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 489,
            "end": 678,
            "exact": "Without specifying quantity role, the report states that a sample length is represented by a quantity whose unit has length dimensionality. The reviewed quantity is sample length = 1 meter.",
            "prefix": "ntity is sample length = 1 meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:outside_validity_domain",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 706,
            "end": 909,
            "exact": "In a different scientific context, the report nevertheless states that a sample length is represented by a quantity whose unit has length dimensionality. The reviewed quantity is sample length = 1 meter.",
            "prefix": "quantity is sample length = 1 meter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:empirical_verification_required",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 945,
            "end": 1161,
            "exact": "For a named realization, the report asserts that a sample length is represented by a quantity whose unit has length dimensionality. No qualified observation is bound. The reviewed quantity is sample length = 1 meter.",
            "prefix": " is sample length = 1 meter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that a sample length is represented "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              },
              {
                "condition_id": "requested_foundation_001_qualified_observation",
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
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:negation",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1174,
            "end": 1326,
            "exact": "It is not true that a sample length is represented by a quantity whose unit has length dimensionality. The reviewed quantity is sample length = 1 meter.",
            "prefix": ". The reviewed quantity is sample length = 1 meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA sample length is represented by a quantity "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:unit_variation",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1345,
            "end": 1522,
            "exact": "A sample length is represented by a quantity whose unit has length dimensionality. The reviewed quantities are sample length = 100 centimeter; sample length reference = 1 meter.",
            "prefix": "reviewed quantity is sample length = 1 meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 100,
                "unit": "centimeter"
              },
              {
                "quantity_kind": "sample_length_reference",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "sample_length",
            "value": 1,
            "unit": "meter"
          },
          {
            "quantity_kind": "sample_length",
            "value": 100,
            "unit": "centimeter"
          }
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1554,
            "end": 1756,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A sample length is represented by a quantity whose unit has length dimensionality”. The reviewed quantity is sample length = 1 meter.",
            "prefix": "mple length reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [
              "ambiguity:common:001"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1554,
            "end": 1756,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A sample length is represented by a quantity whose unit has length dimensionality”. The reviewed quantity is sample length = 1 meter.",
            "prefix": "mple length reference = 1 meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [
              "ambiguity:common:001"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:001",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:001:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:paraphrase",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1771,
            "end": 1951,
            "exact": "In equivalent wording, the document states that a sample length is represented by a quantity whose unit has length dimensionality. The reviewed quantity is sample length = 1 meter.",
            "prefix": "The reviewed quantity is sample length = 1 meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA time interval is not the sample-lengt"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "sample_length"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      },
      {
        "case_id": "sci-case:common:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:001",
        "claim_packet": {
          "claim_id": "claim:common:001:false_red_prevention",
          "document_ref": "qualification-fixture:common:001",
          "document_digest": "sha256:3ae8c07d9161159fc3febd02907c59ec112aa2fb3674526eab610913a51f523c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1976,
            "end": 2113,
            "exact": "A time interval is not the sample-length quantity covered by this dimensional example. The reviewed quantity is sample length = 1 second.",
            "prefix": "ed quantity is sample length = 1 meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:sample-length",
            "relation_kind": "dimensional_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:measurement-unit",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "sample_length",
                "value": 1,
                "unit": "second"
              }
            ],
            "conditions": [
              {
                "condition_id": "quantity_role",
                "value": "time_interval"
              },
              {
                "condition_id": "coverage_scope",
                "value": "sample_length_example"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity",
              "sci:binding:common:unit",
              "sci:binding:common:dimension"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:quantity-unit-dimension"
        ],
        "matrix_rule_id": "sci-rule:common:001"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-001

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
