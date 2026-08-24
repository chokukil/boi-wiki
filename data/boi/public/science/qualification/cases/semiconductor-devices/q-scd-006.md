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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 175,
            "end": 328,
            "exact": "A real ultrathin SiO2 MOS gate below the cited thickness must always have exactly zero gate leakage. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nA real MOS device with ultrathin SiO2 b"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 353,
            "end": 547,
            "exact": "A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying the gate diele"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 578,
            "end": 832,
            "exact": "Without specifying the gate dielectric, the report asserts: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "scale is recorded as 1 nanometer.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a different dielectric or a thic"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 860,
            "end": 1141,
            "exact": "For a different dielectric or a thickness outside the cited limit, the report asserts: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "ss scale is recorded as 1 nanometer.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named fabricated MOS d"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1177,
            "end": 1466,
            "exact": "For a named fabricated MOS device, the report asserts: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. This named result requires measurement. The film thickness scale is recorded as 1 nanometer.",
            "prefix": " is recorded as 1 nanometer.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nUnder the stated scientific conditions, it is not t"
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
                "condition_id": "requested_physical_gate_leakage_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1479,
            "end": 1733,
            "exact": "Under the stated scientific conditions, it is not true that a real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "he film thickness scale is recorded as 1 nanometer.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nA real MOS device with ultrathin SiO2 below t"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1752,
            "end": 2008,
            "exact": "A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The reviewed quantities are film thickness scale = 0.001 micrometer; film thickness scale reference = 1 nanometer.",
            "prefix": "m thickness scale is recorded as 1 nanometer.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "film_thickness_scale_reference",
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2040,
            "end": 2312,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: A rea"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2040,
            "end": 2312,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model”. The reviewed quantity is film thickness scale = 1 nanometer.",
            "prefix": "s scale reference = 1 nanometer.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states: A rea"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2327,
            "end": 2565,
            "exact": "In equivalent wording, the document states: A real MOS device with ultrathin SiO2 below the cited thickness can have nonzero tunneling gate leakage, unlike the ideal zero-current model. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "d quantity is film thickness scale = 1 nanometer.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAn ideal-device model with a perfect in"
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
          "document_ref": "qualification-fixture:semiconductor-devices:006",
          "document_digest": "sha256:53ddf23d2432a368b5353f2641a19c364b7e79a41212704807deb0ad15df8129",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2590,
            "end": 2768,
            "exact": "An ideal-device model with a perfect insulator is not the physical ultrathin SiO2 realization addressed by this leakage rule. The film thickness scale is recorded as 1 nanometer.",
            "prefix": "kness scale is recorded as 1 nanometer.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "ideal_device"
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
