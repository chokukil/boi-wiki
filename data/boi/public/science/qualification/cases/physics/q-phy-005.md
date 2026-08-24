---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-qualification-matrix",
  "title": "Q-PHY-005 public qualification matrix",
  "description": "Ten natural candidate-only cases; no human approval or active-release claim",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:qualification:physics:005",
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
      "ref": "sci-rule:physics:005"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "matrix_id": "sci-matrix:physics:005",
    "standard_id": "Q-PHY-005",
    "rule_id": "sci-rule:physics:005",
    "release_refs": [],
    "cases": [
      {
        "case_id": "sci-case:physics:005:clear_violation",
        "case_kind": "clear_violation",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:clear_violation",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:461f99464e8293f431e519194087696e192104859dc61acaf394a59f9e81dedc",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 115,
            "exact": "A control-volume balance is inherently restricted to fixed steady flow. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:in_scope_consistency",
        "case_kind": "in_scope_consistency",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:in_scope_consistency",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:a5f20d8ed2c593041ba08908a623ed48916067fdfd5f338c18573f28c56688b8",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 160,
            "exact": "The control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:missing_required_condition",
        "case_kind": "missing_required_condition",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:missing_required_condition",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:08e49770cf52177920830f1b413cf0395f9c19ed268f3e8fd506a1fbf387e7d4",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 229,
            "exact": "Without one required scientific condition, the document asserts that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:outside_validity_domain",
        "case_kind": "outside_validity_domain",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:outside_validity_domain",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:7e2544f28f3d2f11743f6949c49c947272ae281bcc29b3780171e9fcec4d3a04",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 234,
            "exact": "For a balance with its boundary fluxes omitted, the document asserts that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "outside_boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "OUTSIDE_VALIDITY_DOMAIN",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:empirical_verification_required",
        "case_kind": "empirical_verification_required",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:empirical_verification_required",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:a13e1db66018b2afc1ff6b7f7693cff8b69fe9cf52f80a28935ace71c11f6b39",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 257,
            "exact": "For a named transient flow rig, the document asserts that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "claim_specificity",
                "value": "equipment_or_numeric"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "EMPIRICAL_VERIFICATION_REQUIRED",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:negation",
        "case_kind": "negation",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:negation",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:7245e7a0eed079120b219dd21e0a786592a7466dd7130dedfd54eb157c16f479",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 180,
            "exact": "It is not true that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "VIOLATION",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:unit_variation",
        "case_kind": "unit_variation",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:unit_variation",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:ca2d63979554d0f5640d1eb7d41d95f3efb430fa89e9a7e877b403fb77210cda",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 168,
            "exact": "The control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1000 millipascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1000,
                "unit": "millipascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ],
        "unit_equivalence": [
          {
            "quantity_kind": "pressure_scale",
            "value": 1,
            "unit": "pascal"
          },
          {
            "quantity_kind": "pressure_scale",
            "value": 1000,
            "unit": "millipascal"
          }
        ]
      },
      {
        "case_id": "sci-case:physics:005:decision_changing_ambiguity",
        "case_kind": "decision_changing_ambiguity",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:decision_changing_ambiguity",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:da2cb1bd3652566a27270d0498549e93bb8fd7785f1cc40ca21cd02d8d59107e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 180,
            "exact": "The document calls the proposition 'Control-volume balance scope' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:physics:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ],
        "alternative_claim_packet": {
          "claim_id": "claim:physics:005:decision_changing_ambiguity:alternative",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:da2cb1bd3652566a27270d0498549e93bb8fd7785f1cc40ca21cd02d8d59107e",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 180,
            "exact": "The document calls the proposition 'Control-volume balance scope' valid without resolving whether it affirms or denies that proposition. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [
              "ambiguity:sci-rule:physics:005:decision_changing_ambiguity"
            ],
            "user_confirmed": false
          }
        },
        "expected_gate": "ambiguity_gate"
      },
      {
        "case_id": "sci-case:physics:005:paraphrase",
        "case_kind": "paraphrase",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:paraphrase",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:98a08a5d6daf58f30ad71573992ae8c60cade72efe230da9e6cf668ed1c67a29",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 183,
            "exact": "In equivalent wording, the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "positive",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "CONSISTENT",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      },
      {
        "case_id": "sci-case:physics:005:false_red_prevention",
        "case_kind": "false_red_prevention",
        "matrix_rule_id": "sci-rule:physics:005",
        "evaluation_rule_id": "sci-rule:physics:005",
        "claim_packet": {
          "claim_id": "claim:physics:005:false_red_prevention",
          "document_ref": "qualification:physics:005",
          "document_digest": "sha256:fe82c5b7f111a9fa014691cd4b7bc541d1b1ce458dfbb72829efe66957673b33",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 0,
            "end": 188,
            "exact": "When the control surface is outside this rule's required scope, the document denies that control volume balance applies to moving unsteady flow. The pressure scale is recorded as 1 pascal.",
            "prefix": "",
            "suffix": ""
          },
          "normalized_claim": {
            "subject_concept_id": "sci:concept:control-volume-balance",
            "relation_kind": "equation",
            "predicate": "applies",
            "object_concept_id": "sci:concept:moving-unsteady-flow",
            "polarity": "negative",
            "quantities": [
              {
                "quantity_kind": "pressure_scale",
                "value": 1,
                "unit": "pascal"
              }
            ],
            "conditions": [
              {
                "condition_id": "control_surface",
                "value": "outside_explicit_closed_surface"
              },
              {
                "condition_id": "flux_accounting",
                "value": "boundary_and_accumulation_terms"
              }
            ],
            "process_stage": null,
            "material_state": null
          },
          "interpretation": {
            "ontology_refs": [
              "sci:binding:domain:angular-speed",
              "sci:binding:domain:viscosity"
            ],
            "ambiguity_ids": [],
            "user_confirmed": true
          }
        },
        "expected_verdict": "INSUFFICIENT_INFORMATION",
        "rationale": "This natural-language claim exercises control-volume balance scope through the target Rule's own typed conditions and Evidence scope.",
        "expected_evidence_path": [
          "sci-evidence:physics:control-volume-flux"
        ]
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# Q-PHY-005

Ten public natural-claim fixtures qualify only `sci-rule:physics:005`. No operational authority is created.
