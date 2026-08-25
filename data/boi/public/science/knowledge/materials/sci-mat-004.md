---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-MAT-004 Arrhenius diffusion temperature direction",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:materials:004",
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
      "ref": "sci-evidence:materials:diffusion-arrhenius"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:materials:004",
    "domain_topic_id": "SCI-MAT-004",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "derived_model",
    "statement": "For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient.",
    "assumptions": [
      "All Rule conditions for sci-rule:materials:004 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:materials:004."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:materials:diffusion-arrhenius"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:materials:diffusion-arrhenius",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equations": [
      {
        "equation_id": "sci:equation:materials:arrhenius-diffusion",
        "scientific_role": "derived_model",
        "decision_use": "explanation_only",
        "semantic_expression": {
          "schema_version": "science-expression/0.1",
          "root": {
            "op": "relation",
            "left": {
              "op": "variable",
              "variable_id": "diffusion_coefficient"
            },
            "right": {
              "op": "multiply",
              "left": {
                "op": "variable",
                "variable_id": "pre_exponential_factor"
              },
              "right": {
                "op": "function",
                "operands": [
                  {
                    "op": "negate",
                    "operand": {
                      "op": "divide",
                      "left": {
                        "op": "variable",
                        "variable_id": "activation_energy"
                      },
                      "right": {
                        "op": "multiply",
                        "left": {
                          "op": "variable",
                          "variable_id": "boltzmann_constant"
                        },
                        "right": {
                          "op": "variable",
                          "variable_id": "absolute_temperature"
                        }
                      }
                    }
                  }
                ],
                "function_name": "exp"
              }
            },
            "relation": "eq"
          }
        },
        "display_latex": "D = D_0 \\exp\\!\\left(-\\frac{E_a}{k_B T}\\right)",
        "plain_text": "D = D0 * exp(-Ea / (kB*T))",
        "accessibility_reading": "Diffusion coefficient equals the pre-exponential factor times the exponential of negative activation energy divided by Boltzmann constant times absolute temperature.",
        "variables": [
          {
            "variable_id": "diffusion_coefficient",
            "symbol": "D",
            "concept_ref": "sci:concept:diffusion-coefficient",
            "quantity_kind": "diffusion_coefficient",
            "dimension": {
              "length": 2,
              "time": -1
            },
            "unit": "meter ** 2 / second",
            "definition": "Diffusion coefficient for the stated mechanism and phase.",
            "domain": "real",
            "sign_constraint": "positive"
          },
          {
            "variable_id": "pre_exponential_factor",
            "symbol": "D₀",
            "concept_ref": "sci:concept:diffusion-pre-exponential-factor",
            "quantity_kind": "diffusion_pre_exponential_factor",
            "dimension": {
              "length": 2,
              "time": -1
            },
            "unit": "meter ** 2 / second",
            "definition": "Arrhenius pre-exponential diffusion factor.",
            "domain": "real",
            "sign_constraint": "positive"
          },
          {
            "variable_id": "activation_energy",
            "symbol": "Eₐ",
            "concept_ref": "sci:concept:diffusion-activation-energy",
            "quantity_kind": "activation_energy",
            "dimension": {
              "mass": 1,
              "length": 2,
              "time": -2
            },
            "unit": "joule",
            "definition": "Activation energy for the stated diffusion mechanism.",
            "domain": "real",
            "sign_constraint": "positive"
          },
          {
            "variable_id": "boltzmann_constant",
            "symbol": "k_B",
            "concept_ref": "sci:concept:boltzmann-constant",
            "quantity_kind": "boltzmann_constant",
            "dimension": {
              "mass": 1,
              "length": 2,
              "time": -2,
              "thermodynamic_temperature": -1
            },
            "unit": "joule / kelvin",
            "definition": "Boltzmann constant.",
            "domain": "real",
            "sign_constraint": "positive"
          },
          {
            "variable_id": "absolute_temperature",
            "symbol": "T",
            "concept_ref": "sci:concept:absolute-temperature",
            "quantity_kind": "absolute_temperature",
            "dimension": {
              "thermodynamic_temperature": 1
            },
            "unit": "kelvin",
            "definition": "Absolute temperature.",
            "domain": "real",
            "sign_constraint": "positive"
          }
        ],
        "assumptions": [
          "D0, activation energy, diffusion mechanism, phase, and temperature range remain the stated model parameters."
        ],
        "applicability": [
          "Arrhenius representation for the cited diffusion mechanism and material state."
        ],
        "invalid_outside": [
          "Mechanism/phase changes, undefined parameters, or an unqualified temperature range."
        ],
        "boundary_conditions": [
          {
            "condition_id": "positive-absolute-temperature",
            "statement": "Absolute temperature must be positive.",
            "variable_id": "absolute_temperature",
            "operator": "gt",
            "value": "0",
            "unit": "kelvin"
          }
        ],
        "approximation": null,
        "empirical_fit": null,
        "original_notation_mapping": [
          {
            "source_symbol": "D",
            "variable_id": "diffusion_coefficient"
          },
          {
            "source_symbol": "D₀",
            "variable_id": "pre_exponential_factor"
          },
          {
            "source_symbol": "Eₐ",
            "variable_id": "activation_energy"
          },
          {
            "source_symbol": "kB",
            "variable_id": "boltzmann_constant"
          },
          {
            "source_symbol": "T",
            "variable_id": "absolute_temperature"
          }
        ],
        "evidence_uses": [
          {
            "evidence_ref": "sci-evidence:materials:diffusion-arrhenius",
            "purpose": "Bind the exact Arrhenius expression; explanation only until a dedicated exponential evaluator is reviewed.",
            "claim_scope_hash": "sha256:0c83d40de943b4e1f3b555b42f13f47c9939a544e0006eab1488990324ebc742",
            "locator": {
              "medium": "pdf",
              "resource_url": "https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/aa1e1cabaa1d4904209040f98b4436a3_MIT3_091F18_REC26.pdf",
              "content_hash": "sha256:ded3970444be9ed9b62f3aef4d90f3ece6687caf336a6894a0b6a17723f6300a",
              "exact": true,
              "section": "Recitation 26 — Arrhenius relationship",
              "pdf_page_index": 1,
              "printed_page": "PDF page 2",
              "equation_label": "Arrhenius relationship"
            },
            "locator_digest": "sha256:b033a1fd4674d0dc6027f735923d5e60aa13cf00b266ff1d7ab4a57f73c4ba94",
            "transcription": {
              "transcription_id": "sci:transcription:materials:arrhenius-diffusion",
              "original_notation": "D = D₀e^(−Eₐ/(kBT))",
              "original_notation_hash": "sha256:e754f54cf8959b8b13ec4b20e7ab5c4d68c5536b4c11c817f035798d9be4c8f6",
              "variable_context": [
                {
                  "source_symbol": "D",
                  "definition": "Diffusion coefficient for the stated mechanism and phase.",
                  "unit_text": "meter ** 2 / second"
                },
                {
                  "source_symbol": "D₀",
                  "definition": "Arrhenius pre-exponential diffusion factor.",
                  "unit_text": "meter ** 2 / second"
                },
                {
                  "source_symbol": "Eₐ",
                  "definition": "Activation energy for the stated diffusion mechanism.",
                  "unit_text": "joule"
                },
                {
                  "source_symbol": "kB",
                  "definition": "Boltzmann constant.",
                  "unit_text": "joule / kelvin"
                },
                {
                  "source_symbol": "T",
                  "definition": "Absolute temperature.",
                  "unit_text": "kelvin"
                }
              ],
              "variable_context_hash": "sha256:30c140cad67fb4c3cdca0d3bb7e9fe99648135905671d5b7d1d154ad0a9a9865",
              "coordinate_convention": "Scalar diffusion coefficient; anisotropic diffusion tensors are outside this expression.",
              "sign_convention": "D, D0, Ea, kB, and absolute temperature are positive.",
              "unit_convention": "The exponent is dimensionless in coherent SI units.",
              "conventions_hash": "sha256:8681f3ebc7461c4fb78d64658e49d81640679b30eeac3883bde7e04f7b205fea",
              "relation_notation": "equals",
              "transcription_method": "ocr_reviewed",
              "review_state": "reviewed",
              "reviewer": "agent:codex-transcription-draft",
              "reviewed_at": "2026-08-25T11:00:00+09:00",
              "semantic_expression_digest": "sha256:1b420c853bedb64733253f2a7c873250e5703599e6d683742f6b30719325d619",
              "transcription_digest": "sha256:b12a10c897cd5c1ffef66c87defd2c067b43872be6680a72955c250d97648fef"
            }
          }
        ],
        "evaluator": null,
        "equation_digest": "sha256:65cf2f1245b30cf30cb8f9c2dc39f3d5ace24360ae92fdbcfca48c825a772a99"
      }
    ]
  }
}
---

# SCI-MAT-004 — Arrhenius diffusion temperature direction

For positive activation energy and unchanged Arrhenius diffusion parameters and mechanism, increasing absolute temperature increases the diffusion coefficient.

Candidate-only draft; authorized Admin review is absent.
