---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-PHY-003 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:physics:003",
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
      "ref": "sci-rule:physics:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:physics:003",
    "standard_id": "Q-PHY-003",
    "rule_id": "sci-rule:physics:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:physics:003:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:clear_violation",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:dd41552fc9086bc549d4e747787bbf200ee14e118aa7207db896029cff3d1222",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 136,
            "exact": "The applied work is 8 joules while the object's kinetic-energy change is reported as 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 8,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:in_scope_consistency",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:27722667c6d9c8441a9980433756405ab806bccb9e62853a8ae2d8091587f05c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 128,
            "exact": "The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:missing_required_condition",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:c949cdb947103f21e11fbc88d15b3cc2e2c0078107a55e43437c321b3171712b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 192,
            "exact": "The report omits a required scientific condition while stating: The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:outside_validity_domain",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:55ef2fc35bc682703b905eaae2906da81a31d28d3b96e829bf3a09b15dcc0f43",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 186,
            "exact": "With part of the applied work omitted, the report states: The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "outside_all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:empirical_verification_required",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:5bf1c96351daae54dad8c44cb82b5f6fd6f0afdb89b789c6c70d8df389047f95",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "For a particular instrumented impact test, the report states: The applied work is 10 joules and the object's kinetic-energy change is also 10 joules; the named result requires measurement. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "requested_work_energy_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:negation",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:df2bda02bbd68e0c940d586b5932c6514e8c777a93a84b1aa097949be13ab512",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 171,
            "exact": "The report denies the equality even though the applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:unit_variation",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:7a4760d8a1fa982534207eb01bda34527123e7883533f0689925003e1b81fb21",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 184,
            "exact": "The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1000 millijoule. The same energy scale is referenced as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1000,
                "unit": "millijoule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "energy_scale_reference",
                "value": 1,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "energy_scale",
            "value": 1,
            "unit": "joule"
          },
          {
            "quantity_kind": "energy_scale",
            "value": 1000,
            "unit": "millijoule"
          }
        ]
      },
      {
        "case_id": "sci-case:physics:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:decision_changing_ambiguity",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:b58f3bacb56a677dcdf40f159e46f66f4e705ea459d4778533a9b9733141e5cf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 305,
            "exact": "A blurred table entry can be read as either 'The applied work is 10 joules and the object's kinetic-energy change is also 10 joules' or 'The applied work is 8 joules while the object's kinetic-energy change is reported as 10 joules', so the equation is unresolved. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
              "ambiguity:sci-rule:physics:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:physics:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:b58f3bacb56a677dcdf40f159e46f66f4e705ea459d4778533a9b9733141e5cf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 305,
            "exact": "A blurred table entry can be read as either 'The applied work is 10 joules and the object's kinetic-energy change is also 10 joules' or 'The applied work is 8 joules while the object's kinetic-energy change is reported as 10 joules', so the equation is unresolved. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 8,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
              "ambiguity:sci-rule:physics:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:physics:003:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:paraphrase",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:4bfe6ca4961c48c1475f88b5abcee8fe95f74f150ef04a07216506b9807ce0db",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 154,
            "exact": "Using equivalent wording, the applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 10,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "explicit_bounded_object"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      },
      {
        "case_id": "sci-case:physics:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:physics:003",
        "evaluation_rule_id": "sci-rule:physics:003",
        "claim_packet": {
          "claim_id": "claim:physics:003:false_red_prevention",
          "document_ref": "qualification:physics:003",
          "document_digest": "sha256:9a09595cffb31ad05de3851af717d3ec6cf167f09fbcb76e3735b1f1d314eeba",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 159,
            "exact": "With no defined object boundary, the report compares work on one collection with the kinetic-energy change of another. The energy scale is recorded as 1 joule.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:applied-force-work",
            "relation_kind": "equation",
            "predicate": "equals",
            "object_concept_id": "sci:concept:kinetic-energy-change",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "energy_scale",
                "value": 1,
                "unit": "joule"
              },
              {
                "quantity_kind": "applied_work",
                "value": 8,
                "unit": "joule"
              },
              {
                "quantity_kind": "kinetic_energy_change",
                "value": 10,
                "unit": "joule"
              }
            ],
            "conditions": [
              {
                "condition_id": "object_system",
                "value": "unbounded_collection"
              },
              {
                "condition_id": "work_accounting",
                "value": "all_applied_work_terms"
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
        "rationale": "This natural-language claim exercises work and kinetic-energy change through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:work-energy-power"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-PHY-003

Ten public natural-claim fixtures qualify only `sci-rule:physics:003`. No operational authority is created.
