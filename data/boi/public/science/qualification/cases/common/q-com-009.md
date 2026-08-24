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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:250e6bb19d33666bd5d3aac7bfc2362dff95c3c7fa45e2f509d0a97fb89f18c2",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 144,
            "exact": "The mass of the identified material particle necessarily changes merely because the particle moves. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:120471abd8a7f533ba50b0bcb55b13f2704d49029a1029c8c742363766807f0a",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 126,
            "exact": "The mass of the identified material particle remains invariant during its motion. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:11c580f8247526a375135e038e339b0a4b9c2fed2a5bb7d726d8585baeef2d43",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 187,
            "exact": "Without specifying particle identity, the report states that the mass of the identified material particle remains invariant during its motion. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:5f25e38a83ec315ca532a682ebba0885e239fbfb7ae542659a36ad575c4d500b",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 197,
            "exact": "In a different scientific context, the report nevertheless states that the mass of the identified material particle remains invariant during its motion. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:3c94e4403c79110796fae9069ed19b4388f67b436ad644429abdd1f98a8166c0",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 210,
            "exact": "For a named realization, the report asserts that the mass of the identified material particle remains invariant during its motion. No qualified observation is bound. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:23dc2ec0539704957917634f7e193d6b278525c8305bd7f8a0320ff9b1bc0845",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 146,
            "exact": "It is not true that the mass of the identified material particle remains invariant during its motion. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:f660f4a271ae95799eac34a26c8d1b17d831600b570650d71903c07f4a204dda",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 153,
            "exact": "The mass of the identified material particle remains invariant during its motion. The same material particle mass is written as 1000 gram and 1 kilogram.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:e5a413d8204013499225f6784fdecaec0a640eb8fbbcbb26949ce0b59b38aeb8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 280,
            "exact": "The wording leaves unresolved whether 'The mass of the identified material particle remains invariant during its motion.' or instead 'The mass of the identified material particle necessarily changes merely because the particle moves.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:e5a413d8204013499225f6784fdecaec0a640eb8fbbcbb26949ce0b59b38aeb8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 280,
            "exact": "The wording leaves unresolved whether 'The mass of the identified material particle remains invariant during its motion.' or instead 'The mass of the identified material particle necessarily changes merely because the particle moves.'. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:c597e4c684f81a4496eba9abde79089db3fc0bfcf86089e6633256f83928aafe",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 174,
            "exact": "In equivalent wording, the document states that the mass of the identified material particle remains invariant during its motion. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
          "document_ref": "qualification:common:009",
          "document_digest": "sha256:655a7e9da5b605666ad1768539990e41be8d81d1473d2981a2a05046629a7234",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 150,
            "exact": "An open control-volume inventory is not the identified material particle whose mass invariance is stated. The quantity kind is recorded as value unit.",
            "prefix": "",
            "suffix": ""
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
