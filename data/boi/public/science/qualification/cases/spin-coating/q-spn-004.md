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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:41bd8064035eb68a130d40d2afba65e0b7cfbd8e93d7c64276ba22bae7a48e97",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 168,
            "exact": "During final coat spin, increasing spin speed increases attainable resist film thickness in drying-limited photoresist spin coating. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:65cc9a279cb1b7cf627dc3247ae63094460eb729f46ab461620ee33b104de8d0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 195,
            "exact": "During final coat spin, attainable photoresist film thickness decreases approximately with the reciprocal square root of spin speed when drying stops the flow. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:5e1d3dad98c1b0c184281b0f11f6e5840a7ad705cfba04f103eb1d39971ebf87",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 125,
            "exact": "The report states a spin-speed direction without identifying the material as photoresist. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:3524a96caa367410ada34b64b960539303579be57ae989aad5cc6521c1cf2c74",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 125,
            "exact": "The qualitative drying-limited relation is asserted to provide an exact equipment recipe. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:fbdaefb0134d2e8739b25d625a2761fd5cc8296379dd7ac223a026f6132e99dc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 155,
            "exact": "The report claims a measured spin-speed and thickness result for a named coater, but no qualified observation is bound. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:391b72b77eb3bbd37511a5ceb1433a0b48f8d198656ed1bbffabe15aa8c1fdfe",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 161,
            "exact": "It is not true that attainable resist film thickness decreases as spin speed increases during drying-limited final coat spin. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:24720826df1840fb11059812bff66eb63d5a39d4a00441398e0ebad18321fb4e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 218,
            "exact": "During final coat spin, attainable photoresist film thickness decreases as spin speed increases when drying stops the flow. The spin rate is recorded as 1 revolution / minute. The same spin rate is referenced as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:d4be7c57fd5c9aa769a9adbe01971e7d3033e7593dffe2437ac1ab6720d50f5e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "The wording leaves unresolved whether increasing spin speed makes the attainable drying-limited resist film thinner or thicker. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:d4be7c57fd5c9aa769a9adbe01971e7d3033e7593dffe2437ac1ab6720d50f5e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 163,
            "exact": "The wording leaves unresolved whether increasing spin speed makes the attainable drying-limited resist film thinner or thicker. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:d4e606100637c52ae49c00e4f71a38e27d920deda3c85dd3ed36163f3f06a9fd",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 146,
            "exact": "Faster final coat spin produces a thinner attainable photoresist film while drying terminates the radial flow. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:spin-coating:004",
          "document_digest": "sha256:7628ac76a3426c4703fe7f7641a6fa74321783c8682eea2a99627a1c97ef150d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 171,
            "exact": "During the dispense stage before rotation, a thicker liquid puddle does not contradict the spin-speed direction during final coat spin. The spin rate is recorded as 1 rpm.",
            "prefix": "",
            "suffix": ""
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
