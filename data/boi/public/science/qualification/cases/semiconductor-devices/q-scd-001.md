---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-SCD-001 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:semiconductor-devices:001",
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
      "ref": "sci-rule:semiconductor-devices:001"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:semiconductor-devices:001",
    "standard_id": "Q-SCD-001",
    "rule_id": "sci-rule:semiconductor-devices:001",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:semiconductor-devices:001:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:clear_violation",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:8575a055f2fcb5282dc48edfa757ab907de74c9c856953479d27c805d2f2bfaf",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 144,
            "exact": "The Fermi function is the number of states rather than their electron occupation probability. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:in_scope_consistency",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:93a63d2c41a5654510504c50c3e16d9ceb26d13b07fa3907083cdfc21032d04f",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 152,
            "exact": "The Fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:missing_required_condition",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:723620792a32d432d59d59658c45ff9b96262749d91a67c6a12f468f0a21ea71",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 221,
            "exact": "Without one required scientific condition, the document asserts that the fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:outside_validity_domain",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:07515fbdfb36d9dbe81fa3fce4be0880c155bd370601d0a95267aed6b718f1be",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 224,
            "exact": "For a record with no identified energy state, the document asserts that the fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "outside_fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:empirical_verification_required",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:ac1fec2663812971a59563590c6f3a91c04a78da438e2de945d342ffcc19b937",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 251,
            "exact": "For a named semiconductor sample, the document asserts that the fermi function is an electron occupation probability for an available state at the stated energy; the named result requires measurement. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:negation",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:73d9a70b6524ac7071fdc80268c5abcfafdee9f3741421b3111b1f0434d152bb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 172,
            "exact": "It is not true that the Fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:unit_variation",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:5c5166aaf12b79a414f72b9e7696bcf7c7a62a30e849afdfc678cc9e60c563b2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "The Fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1000 millielectron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1000,
                "unit": "millielectron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "carrier_energy",
            "value": 1,
            "unit": "electron_volt"
          },
          {
            "quantity_kind": "carrier_energy",
            "value": 1000,
            "unit": "millielectron_volt"
          }
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:decision_changing_ambiguity",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:51a6dfbeab8cbcb78f3866bac62ffb2033357cae69721b6be1a447c84b39b9fb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 187,
            "exact": "The document calls the proposition 'Fermi occupation probability' valid without resolving whether it affirms or denies that proposition. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
              "ambiguity:sci-rule:semiconductor-devices:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:51a6dfbeab8cbcb78f3866bac62ffb2033357cae69721b6be1a447c84b39b9fb",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 187,
            "exact": "The document calls the proposition 'Fermi occupation probability' valid without resolving whether it affirms or denies that proposition. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
              "ambiguity:sci-rule:semiconductor-devices:001:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:paraphrase",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:ee4d4a8d95324f4ba4a78b8d7c542cfa1ce457c840dae15245dac16e42ad7181",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 175,
            "exact": "In equivalent wording, the fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      },
      {
        "case_id": "sci-case:semiconductor-devices:001:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:semiconductor-devices:001",
        "evaluation_rule_id": "sci-rule:semiconductor-devices:001",
        "claim_packet": {
          "claim_id": "claim:semiconductor-devices:001:false_red_prevention",
          "document_ref": "qualification:semiconductor-devices:001",
          "document_digest": "sha256:aa87753898b66a4970335e7780bb03c8ac8e561a3c5c738558221ee8d7fe6475",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 192,
            "exact": "When the energy state is outside this rule's required scope, the document denies that fermi function applies to state occupation probability. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:fermi-function",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:state-occupation-probability",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "carrier_energy",
                "value": 1,
                "unit": "electron_volt"
              }
            ],
            "conditions": [
              {
                "condition_id": "energy_state",
                "value": "outside_bound_available_state"
              },
              {
                "condition_id": "statistics_model",
                "value": "fermi_dirac"
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
        "rationale": "This natural-language claim exercises fermi occupation probability through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:semiconductor-devices:bands-fermi-level"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-SCD-001

Ten public natural-claim fixtures qualify only `sci-rule:semiconductor-devices:001`. No operational authority is created.
