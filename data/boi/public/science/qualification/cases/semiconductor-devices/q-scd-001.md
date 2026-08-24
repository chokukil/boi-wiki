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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 175,
            "end": 319,
            "exact": "The Fermi function is the number of states rather than their electron occupation probability. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe Fermi function is an electron occup"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 344,
            "end": 496,
            "exact": "The Fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": " energy is recorded as 1 electron_volt.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 527,
            "end": 748,
            "exact": "Without one required scientific condition, the document asserts that the fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "y is recorded as 1 electron_volt.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a record with no identified ener"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 776,
            "end": 1000,
            "exact": "For a record with no identified energy state, the document asserts that the fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "ergy is recorded as 1 electron_volt.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named semiconductor sa"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1036,
            "end": 1287,
            "exact": "For a named semiconductor sample, the document asserts that the fermi function is an electron occupation probability for an available state at the stated energy; the named result requires measurement. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "recorded as 1 electron_volt.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that the Fermi function is an electr"
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
                "condition_id": "requested_fermi_occupation_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1300,
            "end": 1472,
            "exact": "It is not true that the Fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": " The carrier energy is recorded as 1 electron_volt.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe Fermi function is an electron occupation "
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1491,
            "end": 1706,
            "exact": "The Fermi function is an electron occupation probability for an available state at the stated energy. The reviewed quantities are carrier energy = 1000 millielectron_volt; carrier energy reference = 1 electron_volt.",
            "prefix": "arrier energy is recorded as 1 electron_volt.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "carrier_energy_reference",
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1738,
            "end": 1968,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The Fermi function is an electron occupation probability for an available state at the stated energy”. The reviewed quantity is carrier energy = 1 electron_volt.",
            "prefix": "rgy reference = 1 electron_volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the fermi function is an e"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1738,
            "end": 1968,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The Fermi function is an electron occupation probability for an available state at the stated energy”. The reviewed quantity is carrier energy = 1 electron_volt.",
            "prefix": "rgy reference = 1 electron_volt.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the fermi function is an e"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1983,
            "end": 2158,
            "exact": "In equivalent wording, the fermi function is an electron occupation probability for an available state at the stated energy. The carrier energy is recorded as 1 electron_volt.",
            "prefix": "wed quantity is carrier energy = 1 electron_volt.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nA continuum energy interval is not a si"
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
          "document_ref": "qualification-fixture:semiconductor-devices:001",
          "document_digest": "sha256:7ac233b98f04582d46ed7877c6d514f126adbcc64d8cf6ce89eb77189684b68d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2183,
            "end": 2351,
            "exact": "A continuum energy interval is not a single bound available state whose occupation probability is given by this rule. The carrier energy is recorded as 1 electron_volt.",
            "prefix": " energy is recorded as 1 electron_volt.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "continuum_energy_interval"
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
