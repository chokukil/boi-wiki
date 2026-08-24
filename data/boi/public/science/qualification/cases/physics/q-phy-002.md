---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-PHY-002 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:physics:002",
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
      "ref": "sci-rule:physics:002"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:physics:002",
    "standard_id": "Q-PHY-002",
    "rule_id": "sci-rule:physics:002",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:physics:002:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:clear_violation",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 161,
            "end": 271,
            "exact": "A nonzero net external force cannot change the defined system momentum. The net force is recorded as 1 newton.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nFor a defined system, a nonzero net ext"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "cannot_change",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:in_scope_consistency",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 296,
            "end": 456,
            "exact": "For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": " The net force is recorded as 1 newton.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the system bou"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:missing_required_condition",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 487,
            "end": 707,
            "exact": "Without specifying the system boundary, the report asserts: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "et force is recorded as 1 newton.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn an accelerating frame that has no"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:outside_validity_domain",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 735,
            "end": 969,
            "exact": "In an accelerating frame that has not been corrected, the report asserts: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "e net force is recorded as 1 newton.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a particular force-senso"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "outside_inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:empirical_verification_required",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1005,
            "end": 1274,
            "exact": "For a particular force-sensor and cart assembly, the report asserts: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. This named result requires measurement. The net force is recorded as 1 newton.",
            "prefix": "rce is recorded as 1 newton.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "requested_momentum_response_observation",
                "value": "unqualified_observation"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:negation",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1287,
            "end": 1507,
            "exact": "Under the stated scientific conditions, it is not true that for a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "measurement. The net force is recorded as 1 newton.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nFor a defined system, a nonzero net external "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:unit_variation",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1526,
            "end": 1737,
            "exact": "For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The reviewed quantities are net force = 1000 millinewton; net force reference = 1 newton.",
            "prefix": "d law. The net force is recorded as 1 newton.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1000,
                "unit": "millinewton"
              },
              {
                "quantity_kind": "net_force_reference",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "net_force",
            "value": 1,
            "unit": "newton"
          },
          {
            "quantity_kind": "net_force",
            "value": 1000,
            "unit": "millinewton"
          }
        ]
      },
      {
        "case_id": "sci-case:physics:002:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1769,
            "end": 2007,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law”. The reviewed quantity is net force = 1 newton.",
            "prefix": " net force reference = 1 newton.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: For a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
              "ambiguity:sci-rule:physics:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:physics:002:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1769,
            "end": 2007,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law”. The reviewed quantity is net force = 1 newton.",
            "prefix": " net force reference = 1 newton.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: For a"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "cannot_change",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
              "ambiguity:sci-rule:physics:002:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:physics:002:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:paraphrase",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2022,
            "end": 2226,
            "exact": "In equivalent wording, the document states: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "”. The reviewed quantity is net force = 1 newton.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA zero net external force cannot change"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "changes",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "resolved_nonzero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      },
      {
        "case_id": "sci-case:physics:002:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:physics:002",
        "evaluation_rule_id": "sci-rule:physics:002",
        "claim_packet": {
          "claim_id": "claim:physics:002:false_red_prevention",
          "document_ref": "qualification-fixture:physics:002",
          "document_digest": "sha256:396b9978ca8d3a0a7be6074d4f591c292f6c26a047e91e54e5d07347c255cc51",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2251,
            "end": 2365,
            "exact": "A zero net external force cannot change the momentum of the defined system. The net force is recorded as 1 newton.",
            "prefix": " The net force is recorded as 1 newton.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:external-force",
            "relation_kind": "causal_relation",
            "predicate": "cannot_change",
            "object_concept_id": "sci:concept:system-momentum",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "net_force",
                "value": 1,
                "unit": "newton"
              }
            ],
            "conditions": [
              {
                "condition_id": "system_boundary",
                "value": "explicit_closed_system"
              },
              {
                "condition_id": "net_external_force",
                "value": "zero_vector"
              },
              {
                "condition_id": "reference_frame",
                "value": "inertial"
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
        "rationale": "This natural-language claim exercises external force changes system momentum through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:force-momentum"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-PHY-002

Ten public natural-claim fixtures qualify only `sci-rule:physics:002`. No operational authority is created.
