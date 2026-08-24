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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 175,
            "end": 533,
            "exact": "Low-field semiconductor conductivity is independent of electron and hole concentrations and mobilities. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nLow-field semiconductor conductivity de"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 558,
            "end": 919,
            "exact": "Low-field semiconductor conductivity depends on the bound electron and hole concentrations and mobilities. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "ctivity 17.623942974 siemens per meter.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nCarrier concentrations and mobili"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 950,
            "end": 1305,
            "exact": "Carrier concentrations and mobilities are listed without identifying the low-field transport regime. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "y 17.623942974 siemens per meter.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nThe low-field carrier-conductivity e"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1333,
            "end": 1685,
            "exact": "The low-field carrier-conductivity equation is asserted as an unchanged high-field transport law. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "vity 17.623942974 siemens per meter.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nThe report claims a measured"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1721,
            "end": 2085,
            "exact": "The report claims a measured low-field conductivity for a named wafer, but no qualified observation is bound. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "623942974 siemens per meter.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that low-field conductivity depends "
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2098,
            "end": 2455,
            "exact": "It is not true that low-field conductivity depends on electron and hole concentrations and mobilities. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "d, and conductivity 17.623942974 siemens per meter.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nIn the low-field regime, electron concentrati"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2474,
            "end": 2876,
            "exact": "In the low-field regime, electron concentration n = 1e21 and hole concentration p = 2e20 per cubic metre, with electron and hole mobilities 0.1 and 0.05 square metres per volt-second, give conductivity 17.623942974 siemens / meter through the carrier-conductivity relation. The reviewed quantities are conductivity scale = 10 millisiemens / centimeter; conductivity scale reference = 1 siemens / meter.",
            "prefix": " conductivity 17.623942974 siemens per meter.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2908,
            "end": 3553,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “In the low-field regime, electron concentration n = 1e21 and hole concentration p = 2e20 per cubic metre, with electron and hole mobilities 0.1 and 0.05 square metres per volt-second, give conductivity 17.623942974 siemens / meter through the carrier-conductivity relation”. The reviewed quantities are conductivity scale = 1 siemens / meter; electron concentration = 1e21 1 / meter ** 3; hole concentration = 2e20 1 / meter ** 3; electron mobility = 0.1 meter ** 2 / volt / second; hole mobility = 0.05 meter ** 2 / volt / second; conductivity = 17.623942974 siemens / meter.",
            "prefix": "e reference = 1 siemens / meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nElectron and hole populations and their mobilitie"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2908,
            "end": 3553,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “In the low-field regime, electron concentration n = 1e21 and hole concentration p = 2e20 per cubic metre, with electron and hole mobilities 0.1 and 0.05 square metres per volt-second, give conductivity 17.623942974 siemens / meter through the carrier-conductivity relation”. The reviewed quantities are conductivity scale = 1 siemens / meter; electron concentration = 1e21 1 / meter ** 3; hole concentration = 2e20 1 / meter ** 3; electron mobility = 0.1 meter ** 2 / volt / second; hole mobility = 0.05 meter ** 2 / volt / second; conductivity = 17.623942974 siemens / meter.",
            "prefix": "e reference = 1 siemens / meter.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nElectron and hole populations and their mobilitie"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 3568,
            "end": 3933,
            "exact": "Electron and hole populations and their mobilities jointly contribute to low-field semiconductor conductivity. The conductivity scale is recorded as 1 siemens / meter. The bound state gives n = 1e21 per cubic meter, p = 2e20 per cubic meter, electron mobility 0.1 and hole mobility 0.05 square meter per volt-second, and conductivity 17.623942974 siemens per meter.",
            "prefix": "ond; conductivity = 17.623942974 siemens / meter.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nIn a high-field transport regime, the r"
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
          "document_ref": "qualification-fixture:semiconductor-devices:003",
          "document_digest": "sha256:cbbdb56aa72f9fe3fe8be1f9ed7abd9cffb4df49ea18987c37b77aecb48ccba8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 3958,
            "end": 4357,
            "exact": "In a high-field transport regime, the report does not apply the low-field carrier-conductivity relation even though electron concentration is 1e21 1 / meter ** 3, hole concentration is 2e20 1 / meter ** 3, electron mobility is 0.1 meter ** 2 / volt / second, hole mobility is 0.05 meter ** 2 / volt / second, conductivity is 17.623942974 siemens / meter, and conductivity scale is 1 siemens / meter.",
            "prefix": "ctivity 17.623942974 siemens per meter.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "condition_id": "relation_context",
                "value": "carrier_conductivity"
              },
              {
                "condition_id": "transport_regime",
                "value": "high_field"
              },
              {
                "condition_id": "carrier_parameter_scope",
                "value": "electron_and_hole_concentrations_and_mobilities"
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
