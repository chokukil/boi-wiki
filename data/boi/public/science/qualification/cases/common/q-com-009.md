---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-COM-009 public qualification matrix",
  "description": "Ten public candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceQualification",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:qualification:common:009",
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
      "ref": "sci-rule:common:009"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:common:009",
    "standard_id": "Q-COM-009",
    "rule_id": "sci-rule:common:009",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:common:009:clear_violation",
        "case_kind": "clear_violation",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:clear_violation",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 160,
            "end": 321,
            "exact": "The mass of the identified material particle necessarily changes merely because the particle moves. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe mass of the identified material par"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "changes_with_motion",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:in_scope_consistency",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 346,
            "end": 489,
            "exact": "The mass of the identified material particle remains invariant during its motion. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "is material particle mass = 1 kilogram.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout specifying particle ident"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:missing_required_condition",
        "case_kind": "missing_required_condition",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:missing_required_condition",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 520,
            "end": 724,
            "exact": "Without specifying particle identity, the report states that the mass of the identified material particle remains invariant during its motion. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "erial particle mass = 1 kilogram.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nIn a different scientific context, t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:outside_validity_domain",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 752,
            "end": 966,
            "exact": "In a different scientific context, the report nevertheless states that the mass of the identified material particle remains invariant during its motion. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "material particle mass = 1 kilogram.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named realization, the"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "different_scientific_context"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:empirical_verification_required",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1002,
            "end": 1229,
            "exact": "For a named realization, the report asserts that the mass of the identified material particle remains invariant during its motion. No qualified observation is bound. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": " particle mass = 1 kilogram.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that the mass of the identified mate"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              },
              {
                "condition_id": "requested_foundation_009_qualified_observation",
                "value": "unqualified_observation"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:model"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:negation",
        "case_kind": "negation",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:negation",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1242,
            "end": 1405,
            "exact": "It is not true that the mass of the identified material particle remains invariant during its motion. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "ed quantity is material particle mass = 1 kilogram.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe mass of the identified material particle "
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:unit_variation",
        "case_kind": "unit_variation",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:unit_variation",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1424,
            "end": 1616,
            "exact": "The mass of the identified material particle remains invariant during its motion. The reviewed quantities are material particle mass = 1000 gram; material particle mass reference = 1 kilogram.",
            "prefix": "ntity is material particle mass = 1 kilogram.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1000,
                "unit": "gram"
              },
              {
                "quantity_kind": "material_particle_mass_reference",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "material_particle_mass",
            "value": 1,
            "unit": "kilogram"
          },
          {
            "quantity_kind": "material_particle_mass",
            "value": 1000,
            "unit": "gram"
          }
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:decision_changing_ambiguity",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1648,
            "end": 1861,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The mass of the identified material particle remains invariant during its motion”. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "cle mass reference = 1 kilogram.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [
              "ambiguity:common:009"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:common:009:decision_changing_ambiguity:alternative",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1648,
            "end": 1861,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The mass of the identified material particle remains invariant during its motion”. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "cle mass reference = 1 kilogram.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the document states that t"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "changes_with_motion",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [
              "ambiguity:common:009"
            ],
            "user_confirmed": false
          }
        },
        "matrix_rule_id": "sci-rule:common:009",
        "expected_verdict": "INSUFFICIENT_INFORMATION"
      },
      {
        "case_id": "sci-case:common:009:paraphrase",
        "case_kind": "paraphrase",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:paraphrase",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1876,
            "end": 2067,
            "exact": "In equivalent wording, the document states that the mass of the identified material particle remains invariant during its motion. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": " quantity is material particle mass = 1 kilogram.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAn open control-volume inventory is not"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "remains_invariant",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "bounded_material_particle"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      },
      {
        "case_id": "sci-case:common:009:false_red_prevention",
        "case_kind": "false_red_prevention",
        "evaluation_rule_id": "sci-rule:common:009",
        "claim_packet": {
          "claim_id": "claim:common:009:false_red_prevention",
          "document_ref": "qualification-fixture:common:009",
          "document_digest": "sha256:d7875197a38436df192b781105da32d07505a37b69f99a12d60e04b20710eb8b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2092,
            "end": 2259,
            "exact": "An open control-volume inventory is not the identified material particle whose mass invariance is stated. The reviewed quantity is material particle mass = 1 kilogram.",
            "prefix": "is material particle mass = 1 kilogram.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:material-particle-mass",
            "relation_kind": "causal_relation",
            "predicate": "changes_with_motion",
            "object_concept_id": "sci:concept:material-particle-motion",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "material_particle_mass",
                "value": 1,
                "unit": "kilogram"
              }
            ],
            "conditions": [
              {
                "condition_id": "particle_identity",
                "value": "open_control_volume_inventory"
              },
              {
                "condition_id": "statement_scope",
                "value": "lagrangian_mass_invariance"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:common:quantity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "Natural, source-anchored candidate qualification document for the target Foundation Rule.",
        "expected_evidence_path": [
          "sci-evidence:common:system-balance"
        ],
        "matrix_rule_id": "sci-rule:common:009"
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---
# Q-COM-009

Ten public cases exercise the required qualification kinds against candidate rules only. Synthetic observation fixtures are labeled and never enter operational evidence.
