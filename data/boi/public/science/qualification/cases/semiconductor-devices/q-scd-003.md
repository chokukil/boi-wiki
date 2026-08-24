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
          "document_digest": "sha256:0071decce73c14fc539195e636ece6974a72a5ed3e146adec824a895fff1a697",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 358,
            "exact": "Low-field semiconductor conductivity is independent of electron and hole concentrations and mobilities. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:29d554af9fc3fbe3b9be0954de179f05db4831d48406b92d85fc4a64145eafea",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 361,
            "exact": "Low-field semiconductor conductivity depends on the bound electron and hole concentrations and mobilities. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:1cc4a1ffdc0ce96144008b6a6d0f078c953828e78ce5e85754b60bc137313f1d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 355,
            "exact": "Carrier concentrations and mobilities are listed without identifying the low-field transport regime. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:cae6c810fca75e4c4d3b60f00525a9cf364c9853e81dfcba060b286138083294",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 352,
            "exact": "The low-field carrier-conductivity equation is asserted as an unchanged high-field transport law. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
              },
              {
                "condition_id": "relation_context",
                "value": "high_field_transport"
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
          "document_digest": "sha256:451d649fe056488451efa5e37afa4b308057c9e067f405bf64f848bb9cdd99d7",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 364,
            "exact": "The report claims a measured low-field conductivity for a named wafer, but no qualified observation is bound. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
              },
              {
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              },
              {
                "condition_id": "requested_carrier_conductivity_observation",
                "value": "unqualified_observation"
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
          "document_digest": "sha256:e2714520eeba87a207bc2374f7d7648db98cdcc8650603320b2525db8862859f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 357,
            "exact": "It is not true that low-field conductivity depends on electron and hole concentrations and mobilities. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:e6c8a457594a65dbd411c81157808f2200ccd05f53ecdd1a035188e6613e6631",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 436,
            "exact": "Low-field semiconductor conductivity depends on the bound electron and hole concentrations and mobilities. The conductivity scale is recorded as 10 millisiemens / centimeter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter. The same conductivity scale is referenced as 1 siemens / meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 10,
                "unit": "millisiemens / centimeter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "conductivity_scale_reference",
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
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:41f7273260454eb40122a6342c479bdefe98708f34dd1aed522a053bd672d600",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 371,
            "exact": "The wording leaves unresolved whether carrier concentrations and mobilities do or do not contribute to conductivity. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:41f7273260454eb40122a6342c479bdefe98708f34dd1aed522a053bd672d600",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 371,
            "exact": "The wording leaves unresolved whether carrier concentrations and mobilities do or do not contribute to conductivity. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:9f4c008353f7921ab9dfd9d36d539770f5151322dad6237f7b7667f2308dd82f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 365,
            "exact": "Electron and hole populations and their mobilities jointly contribute to low-field semiconductor conductivity. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
          "document_digest": "sha256:ba080d6ce404d3242ceab7b11063b610ea0b9530cbb52a3eb6686ca8d65f2b9b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 375,
            "exact": "A doping label with no before-and-after carrier concentrations or mobilities cannot establish the conductivity relation. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:carrier-state-parameters",
            "relation_kind": "empirical_relation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:conductivity",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "conductivity_scale",
                "value": 1,
                "unit": "siemens / meter"
              },
              {
                "quantity_kind": "electron_concentration",
                "value": "1e21",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "hole_concentration",
                "value": "2e20",
                "unit": "1 / meter ** 3"
              },
              {
                "quantity_kind": "electron_mobility",
                "value": "0.1",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "hole_mobility",
                "value": "0.05",
                "unit": "meter ** 2 / volt / second"
              },
              {
                "quantity_kind": "conductivity",
                "value": "17.623942974",
                "unit": "siemens / meter"
              }
            ],
            "conditions": [
              {
                "condition_id": "transport_regime",
                "value": "low_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "single_doping_label"
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
