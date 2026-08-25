---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-CHE-001 Molar concentration definition",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:chemistry:001",
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
      "ref": "sci-evidence:chemistry:amount-concentration"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:chemistry:001",
    "domain_topic_id": "SCI-CHE-001",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "knowledge_kind": "model",
    "assurance_basis": "derived_model",
    "statement": "Molar concentration is the amount of solute in moles divided by the solution volume in litres for the stated molarity convention.",
    "assumptions": [
      "All Rule conditions for sci-rule:chemistry:001 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:chemistry:001."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:chemistry:amount-concentration"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:chemistry:amount-concentration",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equations": [
      {
        "equation_id": "sci:equation:chemistry:molar-concentration-definition",
        "scientific_role": "definition",
        "decision_use": "deterministic_rule",
        "semantic_expression": {
          "schema_version": "science-expression/0.1",
          "root": {
            "op": "relation",
            "left": {
              "op": "variable",
              "variable_id": "molar_concentration"
            },
            "right": {
              "op": "divide",
              "left": {
                "op": "variable",
                "variable_id": "solute_amount"
              },
              "right": {
                "op": "variable",
                "variable_id": "solution_volume"
              }
            },
            "relation": "eq"
          }
        },
        "display_latex": "c = \\frac{n_{\\mathrm{solute}}}{V_{\\mathrm{solution}}}",
        "plain_text": "c = n_solute / V_solution",
        "accessibility_reading": "Molar concentration equals solute amount divided by solution volume.",
        "variables": [
          {
            "variable_id": "molar_concentration",
            "symbol": "c",
            "concept_ref": "sci:concept:molar-concentration",
            "quantity_kind": "molar_concentration",
            "dimension": {
              "length": -3,
              "amount_of_substance": 1
            },
            "unit": "mole / liter",
            "definition": "Amount concentration under the molarity convention.",
            "domain": "real",
            "sign_constraint": "any"
          },
          {
            "variable_id": "solute_amount",
            "symbol": "n_solute",
            "concept_ref": "sci:concept:solute-amount",
            "quantity_kind": "solute_amount",
            "dimension": {
              "amount_of_substance": 1
            },
            "unit": "mole",
            "definition": "Amount of the named solute in moles.",
            "domain": "real",
            "sign_constraint": "nonnegative"
          },
          {
            "variable_id": "solution_volume",
            "symbol": "V_solution",
            "concept_ref": "sci:concept:solution-volume",
            "quantity_kind": "solution_volume",
            "dimension": {
              "length": 3
            },
            "unit": "liter",
            "definition": "Final volume of the solution, not solvent volume.",
            "domain": "real",
            "sign_constraint": "positive"
          }
        ],
        "assumptions": [
          "The concentration convention is molarity and the denominator is solution volume."
        ],
        "applicability": [
          "Named solute amount per final solution volume."
        ],
        "invalid_outside": [
          "Other concentration conventions or zero/undefined solution volume."
        ],
        "boundary_conditions": [
          {
            "condition_id": "positive-solution-volume",
            "statement": "Solution volume must be positive.",
            "variable_id": "solution_volume",
            "operator": "gt",
            "value": "0",
            "unit": "liter"
          }
        ],
        "approximation": null,
        "empirical_fit": null,
        "original_notation_mapping": [
          {
            "source_symbol": "Molar concentration (molarity)",
            "variable_id": "molar_concentration"
          },
          {
            "source_symbol": "number of moles of solute",
            "variable_id": "solute_amount"
          },
          {
            "source_symbol": "liter of solution",
            "variable_id": "solution_volume"
          }
        ],
        "evidence_uses": [
          {
            "evidence_ref": "sci-evidence:chemistry:amount-concentration",
            "purpose": "Bind the exact molarity definition and distinguish solution from solvent volume.",
            "claim_scope_hash": "sha256:bc9aa27c6f74f140d80b665094cf71a1df1e6969259b49d9b093499d95f2aaf8",
            "locator": {
              "medium": "html",
              "resource_url": "https://www.chem1.com/acad/webtext/solut/solut-1.html",
              "content_hash": "sha256:f40fc5c0ec0afb3ebb34d21bc2eab905c3675348bf432503256d2fe94eea0013",
              "exact": true,
              "heading": "Molarity: mole/volume basis",
              "sentence_ordinal": 2,
              "equation_label": "Molarity definition sentence (prose)"
            },
            "locator_digest": "sha256:38bd2b3eda5932e72ba1027c748b94f6fb60ee565541e738320a94efac03a7a7",
            "transcription": {
              "transcription_id": "sci:transcription:chemistry:molar-concentration-definition",
              "original_notation": "Molar concentration (molarity) is the number of moles of solute per liter of solution.",
              "original_notation_hash": "sha256:cc6e5355ca7ec415eee52ffffb29d2591a01e1e5f78d8ba0416fb38a3b5c11f3",
              "variable_context": [
                {
                  "source_symbol": "Molar concentration (molarity)",
                  "definition": "Amount concentration under the molarity convention.",
                  "unit_text": "mole / liter"
                },
                {
                  "source_symbol": "number of moles of solute",
                  "definition": "Amount of the named solute in moles.",
                  "unit_text": "mole"
                },
                {
                  "source_symbol": "liter of solution",
                  "definition": "Final volume of the solution, not solvent volume.",
                  "unit_text": "liter"
                }
              ],
              "variable_context_hash": "sha256:5165020d6e6294083f100da35b3b36184a729700a44bb40b9728cea338f26d7a",
              "coordinate_convention": "No spatial coordinate convention is used by this scalar definition.",
              "sign_convention": "Amounts are nonnegative and the solution volume is positive.",
              "unit_convention": "The cited convention is moles of solute per litre of solution.",
              "conventions_hash": "sha256:4a68d5057d26bd6ee2089cb4e78eda6a5f5cab9240a6fef14d9688fd1a5c831c",
              "relation_notation": "definition",
              "transcription_method": "manual",
              "review_state": "reviewed",
              "reviewer": "agent:codex-transcription-draft",
              "reviewed_at": "2026-08-25T11:00:00+09:00",
              "semantic_expression_digest": "sha256:408095fbc8788eb710ac33cd2481f456c18eb431ebf57ed29dac621c9e7d3c02",
              "transcription_digest": "sha256:fe4fa11eb7385abbc5c3ec9a021541064a47281eac1e66c61587c977e16273d7"
            }
          }
        ],
        "evaluator": {
          "evaluator_id": "sci-evaluator:closed-arithmetic-relation",
          "version": "0.1.0",
          "expression_schema_version": "science-expression/0.1",
          "allowed_operators": [
            "divide",
            "relation",
            "variable"
          ],
          "evaluator_digest": "sha256:a2324dddd46cd907539eb675d129edfcee646af75b94763f54a365d54c1276ac"
        },
        "equation_digest": "sha256:2db62840faed18a6fcff923caf83ab6dd489648d6db0d522e5f444e1d4dcbf8a"
      }
    ]
  }
}
---

# SCI-CHE-001 — Molar concentration definition

Molar concentration is the amount of solute in moles divided by the solution volume in litres for the stated molarity convention.

Candidate-only draft; authorized Admin review is absent.
