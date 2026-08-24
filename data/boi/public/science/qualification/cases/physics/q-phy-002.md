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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:99fad1f810de3b5af7aa2e62c334cbdf1714be9d380bd50202fd36742524b423",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 110,
            "exact": "A nonzero net external force cannot change the defined system momentum. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:d1d200a6999feaefac36edfd213c94324c5868abbe4d33a25292026b4a014602",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:5370417392bef7c79c7af03ab4454f4718016b76e45e85703a7b22cf66149eaa",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 220,
            "exact": "Without specifying the system boundary, the report asserts: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:0c9fb2d2816266ef3a995465cdd4fe4136eefb83289c0b0ee7579229ee33311d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 234,
            "exact": "In an accelerating frame that has not been corrected, the report asserts: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:533ebf08f6138f1148442d3d62d1ff9ba0a5737a75cf1094fdf93432202f44da",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 269,
            "exact": "For a particular force-sensor and cart assembly, the report asserts: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. This named result requires measurement. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:c1c58a9912d81266804a0b0fbf130cd42b63c8b31de1a459f0add9dbabbe9e61",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 220,
            "exact": "Under the stated scientific conditions, it is not true that for a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:789f85912c343604c1c95c1d435dbe016a58bb334ef2170f787e48b8dd5c2c86",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 214,
            "exact": "For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1000 millinewton. The same net force is referenced as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:abcadb7b09df73380bf586a141d65bb455683fba1c462be239bfe765c271588a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 285,
            "exact": "The wording leaves unresolved whether 'For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law.' or instead 'A nonzero net external force cannot change the defined system momentum'. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:abcadb7b09df73380bf586a141d65bb455683fba1c462be239bfe765c271588a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 285,
            "exact": "The wording leaves unresolved whether 'For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law.' or instead 'A nonzero net external force cannot change the defined system momentum'. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:d8ba1e61bb38ce9640e8fa6aba897b21c8777ec3233aeafec5f506bb29316313",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 204,
            "exact": "In equivalent wording, the document states: For a defined system, a nonzero net external force causes the system momentum to change according to Newton's second law. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:physics:002",
          "document_digest": "sha256:8b0d6cbee318ca2cf6d88c68dc6089b58afd7d2438eec4f970a92baac1ef896e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 114,
            "exact": "A zero net external force cannot change the momentum of the defined system. The net force is recorded as 1 newton.",
            "prefix": "",
            "suffix": ""
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
