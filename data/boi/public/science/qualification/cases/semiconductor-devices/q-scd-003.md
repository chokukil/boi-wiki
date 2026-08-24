---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SCD-003 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:semiconductor-devices:003",
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
      "ref": "sci-rule:semiconductor-devices:003"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:semiconductor-devices:003",
    "standard_id": "Q-SCD-003",
    "rule_id": "sci-rule:semiconductor-devices:003",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:semiconductor-devices:003:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:clear_violation",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:552ac30350947466a26dce214848d2c7d9e9e4e2418feea8b559fede88beab32",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 145,
            "exact": "Increasing doping always increases conductivity regardless of mobility or carrier state. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:in_scope_consistency",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:4f64e028643c58552d4addd349a7641c8f515a0d38f9ee4f0575694f58e2a7bc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 175,
            "exact": "A doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:missing_required_condition",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:42486f4d9bd8e3eb0221eece8af89a3a9288f84622cfdeae129e4be01a749e92",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 244,
            "exact": "Without one required scientific condition, the document asserts that a doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:outside_validity_domain",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:87f8017b1882ecb434a7279c09c736d3bfbdf8e0379c98652fcc568239b59df6",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 236,
            "exact": "For a high-field transport regime, the document asserts that a doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "outside_carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:empirical_verification_required",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:338cfdfc6854dc5f0e535414b69eea59adae128dbfe52d95dbf80485bda39010",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 286,
            "exact": "For a named implanted wafer after activation, the document asserts that a doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction; the named result requires measurement. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:negation",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:1e91780c8e11afe12a6e9179f401b77dd523f580e178ad22242c6635daa5a6a4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 195,
            "exact": "It is not true that a doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:unit_variation",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:684c433ece3a9e91909bed4d7c0c47d4d4874bd46154164e437677f4d08ad20f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 186,
            "exact": "A doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction. The conductivity scale is recorded as 10 millisiemens / centimeter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 10,
                "unit": "millisiemens / centimeter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "conductivity_scale",
            "value": 1,
            "unit": "siemens / meter"
          },
          {
            "quantity_kind": "conductivity_scale",
            "value": 10,
            "unit": "millisiemens / centimeter"
          }
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:decision_changing_ambiguity",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:a2bcc2c7c6503485d7f2e65beed0df2310371fd5b964c730914f06f3cd344d4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 199,
            "exact": "The document calls the proposition 'Doping, mobility, and conductivity' valid without resolving whether it affirms or denies that proposition. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:semiconductor-devices:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:a2bcc2c7c6503485d7f2e65beed0df2310371fd5b964c730914f06f3cd344d4f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 199,
            "exact": "The document calls the proposition 'Doping, mobility, and conductivity' valid without resolving whether it affirms or denies that proposition. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:semiconductor-devices:003:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:paraphrase",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:991c34d6887d4a65d1f43fe4a24247b90db4105220189dca271d4408afb8189f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 198,
            "exact": "In equivalent wording, a doping change must be evaluated with carrier concentration and mobility before assigning the conductivity direction. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:003:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:semiconductor-devices:003",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:003",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:003:false_red_prevention",
          "document_ref": "qualification:semiconductor-devices:003",
          "document_digest": "sha256:1c32bd018797f2f8254d7c9507ee898a21d0a7143dc537b79e98fb483395ecd3",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 182,
            "exact": "When the doping change is outside this rule's required scope, the document denies that doping change applies to conductivity. The conductivity scale is recorded as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:doping-change",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_state_parameters_known",
                "value": true
              },
              {
                "condition_id": "doping_change",
                "value": "outside_specified_before_after_state"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:semiconductor",
              "sci:binding:domain:mobility",
              "sci:binding:domain:conductivity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises doping, mobility, and conductivity through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:carrier-conductivity"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SCD-003

Ten public natural-claim fixtures qualify only `sci-rule:semiconductor-devices:003`. No operational authority is created.
