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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 161,
            "end": 276,
            "exact": "A control-volume balance is inherently restricted to fixed steady flow. The pressure scale is recorded as 1 pascal.",
            "prefix": "ph is an independently anchored review case.\n\n[clear_violation]\n",
            "suffix": "\n\n[in_scope_consistency]\nThe control-volume form remains applica"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 301,
            "end": 461,
            "exact": "The control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[in_scope_consistency]\n",
            "suffix": "\n\n[missing_required_condition]\nWithout one required scientific c"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 492,
            "end": 721,
            "exact": "Without one required scientific condition, the document asserts that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "re scale is recorded as 1 pascal.\n\n[missing_required_condition]\n",
            "suffix": "\n\n[outside_validity_domain]\nFor a balance with its boundary flux"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 749,
            "end": 983,
            "exact": "For a balance with its boundary fluxes omitted, the document asserts that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "ssure scale is recorded as 1 pascal.\n\n[outside_validity_domain]\n",
            "suffix": "\n\n[empirical_verification_required]\nFor a named transient flow r"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1019,
            "end": 1276,
            "exact": "For a named transient flow rig, the document asserts that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included; the named result requires measurement. The pressure scale is recorded as 1 pascal.",
            "prefix": "ale is recorded as 1 pascal.\n\n[empirical_verification_required]\n",
            "suffix": "\n\n[negation]\nIt is not true that the control-volume form remains"
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
                "condition_id": "requested_control_volume_observation",
                "value": "unqualified_observation"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1289,
            "end": 1469,
            "exact": "It is not true that the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "rement. The pressure scale is recorded as 1 pascal.\n\n[negation]\n",
            "suffix": "\n\n[unit_variation]\nThe control-volume form remains applicable to"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1488,
            "end": 1704,
            "exact": "The control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The reviewed quantities are pressure scale = 1000 millipascal; pressure scale reference = 1 pascal.",
            "prefix": ". The pressure scale is recorded as 1 pascal.\n\n[unit_variation]\n",
            "suffix": "\n\n[decision_changing_ambiguity]\nA smudged yes-or-no mark appears"
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
              },
              {
                "quantity_kind": "pressure_scale_reference",
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1736,
            "end": 1974,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the control-volume form re"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1736,
            "end": 1974,
            "exact": "A smudged yes-or-no mark appears in the margin beside the statement “The control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included”. The reviewed quantity is pressure scale = 1 pascal.",
            "prefix": "sure scale reference = 1 pascal.\n\n[decision_changing_ambiguity]\n",
            "suffix": "\n\n[paraphrase]\nIn equivalent wording, the control-volume form re"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 1989,
            "end": 2172,
            "exact": "In equivalent wording, the control-volume form remains applicable to moving, deforming, and unsteady flow when its flux terms are included. The pressure scale is recorded as 1 pascal.",
            "prefix": "e reviewed quantity is pressure scale = 1 pascal.\n\n[paraphrase]\n",
            "suffix": "\n\n[false_red_prevention]\nAcross an open surface that does not bo"
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
          "document_ref": "qualification-fixture:physics:005",
          "document_digest": "sha256:edcfc31474db177f27e086ed14d5bac279db525b02ad40c9facae5eb7050075d",
          "source_span": {
            "offset_encoding": "unicode_code_point",
            "start": 2197,
            "end": 2346,
            "exact": "Across an open surface that does not bound a control volume, the stated closed-surface balance is denied. The pressure scale is recorded as 1 pascal.",
            "prefix": "pressure scale is recorded as 1 pascal.\n\n[false_red_prevention]\n",
            "suffix": "\n\nEnd of immutable qualification fixture.\n"
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
                "value": "open_surface"
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
