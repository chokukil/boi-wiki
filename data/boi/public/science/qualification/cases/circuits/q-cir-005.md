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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:d8a5fcb6e1c7293fc0abb29faf6591380a677a8634292e2adbf1382e38bef5ff",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 148,
            "exact": "A capacitor's state variable is always inductor current and an inductor's is always capacitor voltage. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:ec692cb2430369e7988062b8f87382bc202e4b74c6ca575164185134c6bebadc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 139,
            "exact": "The capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:65338b7fdeb1ae72fc074794a794a9e2aa4374daa5f17083e41383f982bd2ec9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 208,
            "exact": "Without one required scientific condition, the document asserts that the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:58e4b2aa1e659f3ae65a9fd6b09787aa97af813aca37cc2d76d50a701e9d1a0c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 224,
            "exact": "For an unidentified distributed electromagnetic structure, the document asserts that the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:74294ddf4680cadb17a49d008d539c8fd65e1692f32f98abae42a215c7486975",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 246,
            "exact": "For a named storage component under test, the document asserts that the capacitor voltage and inductor current are their respective lumped-model state variables; the named result requires measurement. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:47237972a4c1e2d109459b74035f10e58975f062b07c330941d33069d89ce218",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 159,
            "exact": "It is not true that the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:f8c78815a77aaf67dbe28261624255191b6b44c1322a11a0afbd54c509551442",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 147,
            "exact": "The capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1000 millifarad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:1b822f4e299d003e4ec14cca90c4d18b7798289a12eac2ddf6b87fcc0a333158",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 192,
            "exact": "The document calls the proposition 'Capacitor and inductor state variables' valid without resolving whether it affirms or denies that proposition. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:1b822f4e299d003e4ec14cca90c4d18b7798289a12eac2ddf6b87fcc0a333158",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 192,
            "exact": "The document calls the proposition 'Capacitor and inductor state variables' valid without resolving whether it affirms or denies that proposition. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:9b92f26e228269f48c34592cdc3f387c1fa87476c525f57310824c4c57e09f98",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 162,
            "exact": "In equivalent wording, the capacitor voltage and inductor current are their respective lumped-model state variables. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:circuits:005",
          "document_digest": "sha256:8457a479177c3c50c856a3a61fcaea999a87580852a7e2689ba97c049f1cee10",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 181,
            "exact": "When the element type is outside this rule's required scope, the document denies that energy storage element applies to state variable. The capacitance scale is recorded as 1 farad.",
            "prefix": "",
            "suffix": ""
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
                "value": "outside_capacitor_or_inductor"
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
