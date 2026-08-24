---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SCD-006 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:semiconductor-devices:006",
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
      "ref": "sci-rule:semiconductor-devices:006"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:semiconductor-devices:006",
    "standard_id": "Q-SCD-006",
    "rule_id": "sci-rule:semiconductor-devices:006",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:semiconductor-devices:006:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:clear_violation",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:5b0e9544dfd590bae51740ae9c24b143df3eba0eea6a93cd78cb986399fc1c96",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 153,
            "exact": "A real ultrathin SiO2 MOS gate below the cited thickness must always have exactly zero gate leakage. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "always_zero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:in_scope_consistency",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:2afb972dd0b4361394528877c16a9cd63f3d687e454e1f2ab8f719ec9b5a0461",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 194,
            "exact": "A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:missing_required_condition",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:4f971d1276e3ce9ead5f69c0755614690f07201cfaffddafc32639006216daf9",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 254,
            "exact": "Without specifying the gate dielectric, the report asserts: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:outside_validity_domain",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:9523e07cb6b4f53376e67c82fe5caaf6ab925a9abfd7e8f69dcf5427e0ba3c6c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 281,
            "exact": "For a different dielectric or a thickness outside the cited limit, the report asserts: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "outside_oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:empirical_verification_required",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:b4c2af6be21feca068dfe57fd7dcdf4e2427478bf5c5a54874acf9435cee5999",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 289,
            "exact": "For a named fabricated MOS device, the report asserts: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. This named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:negation",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:45e9f3f065d3a3de9229ee7cae307f17fdd9dccb962bd32a2ffb5dd776e36aef",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 254,
            "exact": "Under the stated scientific conditions, it is not true that a real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:unit_variation",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:600ca969957b4747e68016689d9a95096f0b73ae82598beb12ff572ae0638685",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 199,
            "exact": "A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 0.001 micrometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": "0.001",
                "unit": "micrometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "film_thickness_scale",
            "value": 1,
            "unit": "nanometer"
          },
          {
            "quantity_kind": "film_thickness_scale",
            "value": "0.001",
            "unit": "micrometer"
          }
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:decision_changing_ambiguity",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:0521d3e22d2fcea6c57c171a8fd760beca16f07233f9d9e17bbcc355ae193ec4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 348,
            "exact": "The wording leaves unresolved whether 'A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model.' or instead 'A real ultrathin SiO2 MOS gate below the cited thickness must always have exactly zero gate leakage'. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
              "ambiguity:sci-rule:semiconductor-devices:006:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:0521d3e22d2fcea6c57c171a8fd760beca16f07233f9d9e17bbcc355ae193ec4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 348,
            "exact": "The wording leaves unresolved whether 'A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model.' or instead 'A real ultrathin SiO2 MOS gate below the cited thickness must always have exactly zero gate leakage'. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "always_zero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
              "ambiguity:sci-rule:semiconductor-devices:006:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:paraphrase",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:6052db8e7bfe27905e57f34f59141cfda4d162e98ca384550f2a47208bc9af39",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 238,
            "exact": "In equivalent wording, the document states: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "can_be_nonzero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:006:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:semiconductor-devices:006",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:006",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:006:false_red_prevention",
          "document_ref": "qualification:semiconductor-devices:006",
          "document_digest": "sha256:1267d6f289f2995c4510c4ee37d5a1cd619e555b191356dac33d270f8f7af50c",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 195,
            "exact": "When the device realization is outside this rule's required scope, the document states that real ultrathin sio2 gate always zero gate leakage. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:real-ultrathin-sio2-gate",
            "relation_kind": "causal_relation",
            "predicate": "always_zero",
            "object_concept_id": "sci:concept:gate-leakage",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "film_thickness_scale",
                "value": 1,
                "unit": "nanometer"
              }
            ],
            "conditions": [
              {
                "condition_id": "gate_dielectric",
                "value": "SiO2"
              },
              {
                "condition_id": "oxide_thickness_nm",
                "value": 1.0,
                "unit": "nm"
              },
              {
                "condition_id": "device_realization",
                "value": "outside_physical_device"
              },
              {
                "condition_id": "leakage_mechanism",
                "value": "oxide_tunneling"
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
        "rationale": "This natural-language claim exercises real ultrathin sio2 gate leakage through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:mos-gate-real-leakage"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SCD-006

Ten public natural-claim fixtures qualify only `sci-rule:semiconductor-devices:006`. No operational authority is created.
