---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SPN-004 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:spin-coating:004",
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
      "ref": "sci-rule:spin-coating:004"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:spin-coating:004",
    "standard_id": "Q-SPN-004",
    "rule_id": "sci-rule:spin-coating:004",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:spin-coating:004:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:clear_violation",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 166,
            "end": 334,
            "exact": "During final coat spin, increasing spin speed increases attainable resist film thickness in drying-limited photoresist spin coating. The spin rate is recorded as 1 rpm.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nDuring final coat spin, attainable phot"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:in_scope_consistency",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 359,
            "end": 554,
            "exact": "During final coat spin, attainable photoresist film thickness decreases approximately with the reciprocal square root of spin speed when drying stops the flow. The spin rate is recorded as 1 rpm.",
            "prefix": "ng. The spin rate is recorded as 1 rpm.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nThe report states a spin-speed di"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:missing_required_condition",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 585,
            "end": 710,
            "exact": "The report states a spin-speed direction without identifying the material as photoresist. The spin rate is recorded as 1 rpm.",
            "prefix": "e spin rate is recorded as 1 rpm.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nThe qualitative drying-limited relat"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:outside_validity_domain",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 738,
            "end": 863,
            "exact": "The qualitative drying-limited relation is asserted to provide an exact equipment recipe. The spin rate is recorded as 1 rpm.",
            "prefix": " The spin rate is recorded as 1 rpm.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nThe report claims a measured"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "exact_equipment_recipe"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:empirical_verification_required",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 899,
            "end": 1054,
            "exact": "The report claims a measured spin-speed and thickness result for a named coater, but no qualified observation is bound. The spin rate is recorded as 1 rpm.",
            "prefix": "n rate is recorded as 1 rpm.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that attainable resist film thicknes"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              },
              {
                "condition_id": "requested_spin_thickness_observation",
                "value": "unqualified_observation"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:negation",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1067,
            "end": 1228,
            "exact": "It is not true that attainable resist film thickness decreases as spin speed increases during drying-limited final coat spin. The spin rate is recorded as 1 rpm.",
            "prefix": "ation is bound. The spin rate is recorded as 1 rpm.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nDuring final coat spin, attainable photoresis"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:unit_variation",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1247,
            "end": 1498,
            "exact": "During final coat spin, attainable photoresist film thickness decreases approximately with the reciprocal square root of spin speed when drying stops the flow. The reviewed quantities are spin rate = 1 revolution / minute; spin rate reference = 1 rpm.",
            "prefix": "oat spin. The spin rate is recorded as 1 rpm.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "revolution / minute"
              },
              {
                "quantity_kind": "spin_rate_reference",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "spin_rate",
            "value": 1,
            "unit": "rpm"
          },
          {
            "quantity_kind": "spin_rate",
            "value": 1,
            "unit": "revolution / minute"
          }
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1530,
            "end": 1803,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “During final coat spin, attainable photoresist film thickness decreases approximately with the reciprocal square root of spin speed when drying stops the flow”. The reviewed quantity is spin rate = 1 rpm.",
            "prefix": "te; spin rate reference = 1 rpm.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nFaster final coat spin produces a thinner attaina"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:spin-coating:004:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1530,
            "end": 1803,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “During final coat spin, attainable photoresist film thickness decreases approximately with the reciprocal square root of spin speed when drying stops the flow”. The reviewed quantity is spin rate = 1 rpm.",
            "prefix": "te; spin rate reference = 1 rpm.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nFaster final coat spin produces a thinner attaina"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:spin-coating:004:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:spin-coating:004:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:paraphrase",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1818,
            "end": 1964,
            "exact": "Faster final coat spin produces a thinner attainable photoresist film while drying terminates the radial flow. The spin rate is recorded as 1 rpm.",
            "prefix": "low”. The reviewed quantity is spin rate = 1 rpm.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nDuring a low-speed dispense stage, incr"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "decreases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "final_coat_spin",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      },
      {
        "case_id": "sci-case:spin-coating:004:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:spin-coating:004",
        "evaluation_rule_id": "sci-rule:spin-coating:004",
        "claim_packet": {
          "claim_id": "claim:spin-coating:004:false_red_prevention",
          "document_ref": "qualification-fixture:spin-coating:004",
          "document_digest": "sha256:dd79f37053305f160cde379172eed05214636667ba4e1ef2bb00efd374da9b18",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1989,
            "end": 2168,
            "exact": "During a low-speed dispense stage, increasing spin speed increases transient liquid-puddle thickness because the dispense rate rises concurrently; the recorded spin_rate is 1 rpm.",
            "prefix": "ow. The spin rate is recorded as 1 rpm.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:spin-speed",
            "relation_kind": "monotonic_direction",
            "predicate": "increases",
            "object_concept_id": "sci:concept:film-thickness",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "spin_rate",
                "value": 1,
                "unit": "rpm"
              }
            ],
            "conditions": [
              {
                "condition_id": "material_class",
                "value": "photoresist"
              },
              {
                "condition_id": "process_method",
                "value": "spin_coating"
              },
              {
                "condition_id": "thinning_continues_until",
                "value": "drying_stops_flow"
              },
              {
                "condition_id": "claim_scope",
                "value": "qualitative_direction_only"
              }
            ],
            "process_stage": "dispense_stage",
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:spin-speed",
              "sci:binding:domain:film-thickness",
              "sci:binding:domain:photoresist"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises product-scoped spin-speed direction through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-SPN-004

Ten public natural-claim fixtures qualify only `sci-rule:spin-coating:004`. No operational authority is created.
