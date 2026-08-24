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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 161,
            "end": 297,
            "exact": "The applied work is 8 joules while the object's kinetic-energy change is reported as 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe applied work is 10 joules and the o"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 322,
            "end": 450,
            "exact": "The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "he energy scale is recorded as 1 joule.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report omits a required scien"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 481,
            "end": 673,
            "exact": "The report omits a required scientific condition while stating: The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "rgy scale is recorded as 1 joule.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nWith part of the applied work omitte"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 701,
            "end": 887,
            "exact": "With part of the applied work omitted, the report states: The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "energy scale is recorded as 1 joule.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a particular instrumente"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 923,
            "end": 1152,
            "exact": "For a particular instrumented impact test, the report states: The applied work is 10 joules and the object's kinetic-energy change is also 10 joules; the named result requires measurement. The energy scale is recorded as 1 joule.",
            "prefix": "cale is recorded as 1 joule.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nThe report denies the equality even though the appl"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1165,
            "end": 1336,
            "exact": "The report denies the equality even though the applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "asurement. The energy scale is recorded as 1 joule.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe applied work is 10 joules and the object'"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1355,
            "end": 1536,
            "exact": "The applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The reviewed quantities are energy scale = 1000 millijoule; energy scale reference = 1 joule.",
            "prefix": "les. The energy scale is recorded as 1 joule.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1568,
            "end": 1836,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The applied work is 10 joules and the object's kinetic-energy change is also 10 joules”. The reviewed quantities are energy scale = 1 joule; applied work = 10 joule; kinetic energy change = 10 joule.",
            "prefix": "nergy scale reference = 1 joule.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, the applied work is 10 "
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1568,
            "end": 1836,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The applied work is 10 joules and the object's kinetic-energy change is also 10 joules”. The reviewed quantities are energy scale = 1 joule; applied work = 10 joule; kinetic energy change = 10 joule.",
            "prefix": "nergy scale reference = 1 joule.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nUsing equivalent wording, the applied work is 10 "
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1851,
            "end": 2005,
            "exact": "Using equivalent wording, the applied work is 10 joules and the object's kinetic-energy change is also 10 joules. The energy scale is recorded as 1 joule.",
            "prefix": "ork = 10 joule; kinetic energy change = 10 joule.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nWith no defined object boundary, the re"
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
          "document_ref": "qualification-fixture:physics:003",
          "document_digest": "sha256:8cb8e71faadd4d5e4889289ae4a35abde62ce9d7f70ed1dbdb3c01f93e92be8a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2030,
            "end": 2189,
            "exact": "With no defined object boundary, the report compares work on one collection with the kinetic-energy change of another. The energy scale is recorded as 1 joule.",
            "prefix": "he energy scale is recorded as 1 joule.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
