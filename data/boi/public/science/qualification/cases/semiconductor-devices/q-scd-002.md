---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SCD-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:semiconductor-devices:002",
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
      "ref": "sci-rule:semiconductor-devices:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:semiconductor-devices:002",
    "standard_id": "Q-SCD-002",
    "rule_id": "sci-rule:semiconductor-devices:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:semiconductor-devices:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:clear_violation",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:d9a3c70b685f7353e0ff1d38b89bb574adfff3b49afeff0549231d9ea3f9a654",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 125,
            "exact": "Semiconductor carrier current can only have drift and never a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:in_scope_consistency",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:c846af055aa5165ed1b86effeb5c68d0429b2667244cd25a89e25d3239c65fb2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 120,
            "exact": "Carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:missing_required_condition",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:2c01746aad619a104a1f9b7eab6a011537e9ab646cbe9cdfc557354364c3b8f9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 189,
            "exact": "Without one required scientific condition, the document asserts that carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:outside_validity_domain",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:3a624efb40c4cfca9265aa12633f163c2b52355e13639a70688d82c19927edd4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 205,
            "exact": "For a transport statement with no carrier type identified, the document asserts that carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "outside_drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:empirical_verification_required",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:03227c58e4f91b9606f480fe790927bfffb35a14e25fa9fcfc14e93ba97b5e60",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 233,
            "exact": "For a named nonuniform semiconductor structure, the document asserts that carrier current can contain both a drift component and a diffusion component; the named result requires measurement. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "requested_carrier_transport_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:negation",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:7aa9df83cbaa7d9998afaabefdee939f0a918cbfb39eeda21386cd4aae620a53",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 140,
            "exact": "It is not true that carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:unit_variation",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:25e48f44f037ea0bc5a09d3642148c74b91d54b2234e8d19bc94759b8116a487",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 178,
            "exact": "Carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1000 milliampere. The same current scale is referenced as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1000,
                "unit": "milliampere"
              },
              {
                "quantity_kind": "current_scale_reference",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "current_scale",
            "value": 1,
            "unit": "ampere"
          },
          {
            "quantity_kind": "current_scale",
            "value": 1000,
            "unit": "milliampere"
          }
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:decision_changing_ambiguity",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:1b9342d373ce9d7b03f73aac0de4e28557c0601accbb2692eaeff57e8f6c2c3e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 189,
            "exact": "The document calls the proposition 'Drift and diffusion current components' valid without resolving whether it affirms or denies that proposition. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
              "ambiguity:sci-rule:semiconductor-devices:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:1b9342d373ce9d7b03f73aac0de4e28557c0601accbb2692eaeff57e8f6c2c3e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 189,
            "exact": "The document calls the proposition 'Drift and diffusion current components' valid without resolving whether it affirms or denies that proposition. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
              "ambiguity:sci-rule:semiconductor-devices:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:paraphrase",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:2d03a8558d3ef4c04f056748db28945f64a4b6542f1762e04f0f3f20d1efddb8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 143,
            "exact": "In equivalent wording, carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "electron_or_hole"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:semiconductor-devices:002",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:002",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:002:false_red_prevention",
          "document_ref": "qualification:semiconductor-devices:002",
          "document_digest": "sha256:9111ed28010d70a499ac800fca3ed0a15727f2cfce7dd8f31bf1cf3848bb40ae",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 139,
            "exact": "Ionic-species current is not the electron-or-hole current decomposed by this semiconductor rule. The current scale is recorded as 1 ampere.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-current",
            "relation_kind": "causal_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:drift-diffusion-components",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "current_scale",
                "value": 1,
                "unit": "ampere"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_type",
                "value": "ionic_species"
              },
              {
                "condition_id": "transport_decomposition",
                "value": "drift_and_diffusion"
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
        "rationale": "This natural-language claim exercises drift and diffusion current components through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:drift-diffusion"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SCD-002

Ten public natural-claim fixtures qualify only `sci-rule:semiconductor-devices:002`. No operational authority is created.
