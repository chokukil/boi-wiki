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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 175,
            "end": 300,
            "exact": "Semiconductor carrier current can only have drift and never a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nCarrier current can contain both a drif"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 325,
            "end": 445,
            "exact": "Carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": " current scale is recorded as 1 ampere.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 476,
            "end": 665,
            "exact": "Without one required scientific condition, the document asserts that carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "nt scale is recorded as 1 ampere.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a transport statement with no ca"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 693,
            "end": 898,
            "exact": "For a transport statement with no carrier type identified, the document asserts that carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "rrent scale is recorded as 1 ampere.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named nonuniform semic"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 934,
            "end": 1167,
            "exact": "For a named nonuniform semiconductor structure, the document asserts that carrier current can contain both a drift component and a diffusion component; the named result requires measurement. The current scale is recorded as 1 ampere.",
            "prefix": "ale is recorded as 1 ampere.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that carrier current can contain bot"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1180,
            "end": 1320,
            "exact": "It is not true that carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "urement. The current scale is recorded as 1 ampere.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nCarrier current can contain both a drift comp"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1339,
            "end": 1514,
            "exact": "Carrier current can contain both a drift component and a diffusion component. The reviewed quantities are current scale = 1000 milliampere; current scale reference = 1 ampere.",
            "prefix": "t. The current scale is recorded as 1 ampere.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1546,
            "end": 1744,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Carrier current can contain both a drift component and a diffusion component”. The reviewed quantity is current scale = 1 ampere.",
            "prefix": "rent scale reference = 1 ampere.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, carrier current can contai"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1546,
            "end": 1744,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “Carrier current can contain both a drift component and a diffusion component”. The reviewed quantity is current scale = 1 ampere.",
            "prefix": "rent scale reference = 1 ampere.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, carrier current can contai"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1759,
            "end": 1902,
            "exact": "In equivalent wording, carrier current can contain both a drift component and a diffusion component. The current scale is recorded as 1 ampere.",
            "prefix": "he reviewed quantity is current scale = 1 ampere.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nIonic-species current is not the electr"
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
          "document_ref": "qualification-fixture:semiconductor-devices:002",
          "document_digest": "sha256:630a4b09d77c9b68f13feb5f97cc85478f9231ce481f6f36dc1df2acba58fefd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1927,
            "end": 2066,
            "exact": "Ionic-species current is not the electron-or-hole current decomposed by this semiconductor rule. The current scale is recorded as 1 ampere.",
            "prefix": " current scale is recorded as 1 ampere.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
