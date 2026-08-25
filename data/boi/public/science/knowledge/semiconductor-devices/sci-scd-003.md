---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-SCD-003 Low-field carrier conductivity",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:semiconductor-devices:003",
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
      "ref": "sci-evidence:semiconductor-devices:carrier-conductivity"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:semiconductor-devices:003",
    "domain_topic_id": "SCI-SCD-003",
    "pack_id": "sci-pack:semiconductor-devices/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "hypothesis",
    "statement": "In the cited low-field relation, semiconductor conductivity is σ = qnµn + qpµp and therefore depends on the bound electron and hole concentrations and mobilities.",
    "assumptions": [
      "All Rule conditions for sci-rule:semiconductor-devices:003 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:semiconductor-devices:003."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:semiconductor-devices:carrier-conductivity"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:semiconductor-devices:carrier-conductivity",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equations": [
      {
        "equation_id": "sci:equation:semiconductor:low-field-conductivity",
        "scientific_role": "derived_model",
        "decision_use": "explanation_only",
        "semantic_expression": {
          "schema_version": "science-expression/0.1",
          "root": {
            "op": "relation",
            "left": {
              "op": "variable",
              "variable_id": "conductivity"
            },
            "right": {
              "op": "add",
              "left": {
                "op": "multiply",
                "left": {
                  "op": "multiply",
                  "left": {
                    "op": "variable",
                    "variable_id": "elementary_charge"
                  },
                  "right": {
                    "op": "variable",
                    "variable_id": "electron_concentration"
                  }
                },
                "right": {
                  "op": "variable",
                  "variable_id": "electron_mobility"
                }
              },
              "right": {
                "op": "multiply",
                "left": {
                  "op": "multiply",
                  "left": {
                    "op": "variable",
                    "variable_id": "elementary_charge"
                  },
                  "right": {
                    "op": "variable",
                    "variable_id": "hole_concentration"
                  }
                },
                "right": {
                  "op": "variable",
                  "variable_id": "hole_mobility"
                }
              }
            },
            "relation": "eq"
          }
        },
        "display_latex": "\\sigma = q n \\mu_n + q p \\mu_p",
        "plain_text": "sigma = q*n*mu_n + q*p*mu_p",
        "accessibility_reading": "Conductivity equals elementary charge times electron concentration times electron mobility, plus elementary charge times hole concentration times hole mobility.",
        "variables": [
          {
            "variable_id": "conductivity",
            "symbol": "σ",
            "concept_ref": "sci:concept:semiconductor-conductivity",
            "quantity_kind": "conductivity",
            "dimension": {
              "mass": -1,
              "length": -3,
              "time": 3,
              "electric_current": 2
            },
            "unit": "siemens / meter",
            "definition": "Low-field semiconductor conductivity.",
            "domain": "real",
            "sign_constraint": "nonnegative"
          },
          {
            "variable_id": "elementary_charge",
            "symbol": "q",
            "concept_ref": "sci:concept:elementary-charge",
            "quantity_kind": "electric_charge",
            "dimension": {
              "time": 1,
              "electric_current": 1
            },
            "unit": "coulomb",
            "definition": "Magnitude of elementary charge.",
            "domain": "real",
            "sign_constraint": "positive"
          },
          {
            "variable_id": "electron_concentration",
            "symbol": "n",
            "concept_ref": "sci:concept:electron-concentration",
            "quantity_kind": "electron_concentration",
            "dimension": {
              "length": -3
            },
            "unit": "1 / meter ** 3",
            "definition": "Electron concentration.",
            "domain": "real",
            "sign_constraint": "nonnegative"
          },
          {
            "variable_id": "electron_mobility",
            "symbol": "μ_n",
            "concept_ref": "sci:concept:electron-mobility",
            "quantity_kind": "electron_mobility",
            "dimension": {
              "mass": -1,
              "time": 2,
              "electric_current": 1
            },
            "unit": "meter ** 2 / volt / second",
            "definition": "Electron mobility in the cited low-field model.",
            "domain": "real",
            "sign_constraint": "nonnegative"
          },
          {
            "variable_id": "hole_concentration",
            "symbol": "p",
            "concept_ref": "sci:concept:hole-concentration",
            "quantity_kind": "hole_concentration",
            "dimension": {
              "length": -3
            },
            "unit": "1 / meter ** 3",
            "definition": "Hole concentration.",
            "domain": "real",
            "sign_constraint": "nonnegative"
          },
          {
            "variable_id": "hole_mobility",
            "symbol": "μ_p",
            "concept_ref": "sci:concept:hole-mobility",
            "quantity_kind": "hole_mobility",
            "dimension": {
              "mass": -1,
              "time": 2,
              "electric_current": 1
            },
            "unit": "meter ** 2 / volt / second",
            "definition": "Hole mobility in the cited low-field model.",
            "domain": "real",
            "sign_constraint": "nonnegative"
          }
        ],
        "assumptions": [
          "Carrier transport is in the cited low-field drift regime."
        ],
        "applicability": [
          "The stated carrier concentrations and mobilities under the low-field model."
        ],
        "invalid_outside": [
          "High-field transport or missing carrier/mobility definitions."
        ],
        "boundary_conditions": [],
        "approximation": null,
        "empirical_fit": null,
        "original_notation_mapping": [
          {
            "source_symbol": "σ",
            "variable_id": "conductivity"
          },
          {
            "source_symbol": "q",
            "variable_id": "elementary_charge"
          },
          {
            "source_symbol": "n",
            "variable_id": "electron_concentration"
          },
          {
            "source_symbol": "µn",
            "variable_id": "electron_mobility"
          },
          {
            "source_symbol": "p",
            "variable_id": "hole_concentration"
          },
          {
            "source_symbol": "µp",
            "variable_id": "hole_mobility"
          }
        ],
        "evidence_uses": [
          {
            "evidence_ref": "sci-evidence:semiconductor-devices:carrier-conductivity",
            "purpose": "Bind the exact low-field conductivity expression; explanation only until a dedicated evaluator is reviewed.",
            "claim_scope_hash": "sha256:e9496ec9e637423f0a2eb739a5d2af1f027f11158041c76ebfc2491e9632ab57",
            "locator": {
              "medium": "pdf",
              "resource_url": "https://www.chu.berkeley.edu/wp-content/uploads/2020/01/Chenming-Hu_ch2-2.pdf",
              "content_hash": "sha256:af37b00ce074935c54c88d27af5c8dceac5bc9b900085ef66c1e863b0b291e98",
              "exact": true,
              "section": "Chapter 2, 2.2 Drift, equation (2.2.14)",
              "pdf_page_index": 9,
              "printed_page": "printed page 44; PDF page 10",
              "equation_label": "Equation (2.2.14)"
            },
            "locator_digest": "sha256:75d495d602ad57ce3d0983e54357ddf3a561dbe66fce7f6935e1df238244d7a7",
            "transcription": {
              "transcription_id": "sci:transcription:semiconductor:low-field-conductivity",
              "original_notation": "σ = qnµn + qpµp",
              "original_notation_hash": "sha256:3b3bd24d4afa08fbc97599d1f6f19d80bc99fce4b56e86a5b6c882b73742556d",
              "variable_context": [
                {
                  "source_symbol": "σ",
                  "definition": "Low-field semiconductor conductivity.",
                  "unit_text": "siemens / meter"
                },
                {
                  "source_symbol": "q",
                  "definition": "Magnitude of elementary charge.",
                  "unit_text": "coulomb"
                },
                {
                  "source_symbol": "n",
                  "definition": "Electron concentration.",
                  "unit_text": "1 / meter ** 3"
                },
                {
                  "source_symbol": "µn",
                  "definition": "Electron mobility in the cited low-field model.",
                  "unit_text": "meter ** 2 / volt / second"
                },
                {
                  "source_symbol": "p",
                  "definition": "Hole concentration.",
                  "unit_text": "1 / meter ** 3"
                },
                {
                  "source_symbol": "µp",
                  "definition": "Hole mobility in the cited low-field model.",
                  "unit_text": "meter ** 2 / volt / second"
                }
              ],
              "variable_context_hash": "sha256:6f1db881c931811a3dc849301f350fc819dc9659748a9be43fd51a5536857f58",
              "coordinate_convention": "Scalar isotropic conductivity form; tensor directions are outside this expression.",
              "sign_convention": "q is the positive elementary-charge magnitude and concentrations/mobilities are nonnegative.",
              "unit_convention": "Coherent SI units produce conductivity in siemens per metre.",
              "conventions_hash": "sha256:eb238cfe2f902cd3ab850545d6ae3f4996e81aa3692332bd0724e7a76ee4a4db",
              "relation_notation": "equals",
              "transcription_method": "manual",
              "review_state": "reviewed",
              "reviewer": "agent:codex-transcription-draft",
              "reviewed_at": "2026-08-25T11:00:00+09:00",
              "semantic_expression_digest": "sha256:d83afe00a62b608fc32b32224aa28ce5a17b320f60aba00ea13104257e356984",
              "transcription_digest": "sha256:430a077f5cf4f1f774a774e7993e0f17a56ad259878c5d48acd7a31189561fea"
            }
          }
        ],
        "evaluator": null,
        "equation_digest": "sha256:0a4901af68c18a20902cd760f5b5fa55e81c7651510c2094fc9ad790e3cf4766"
      }
    ]
  }
}
---

# SCI-SCD-003 Low-field carrier conductivity

In the cited low-field relation, semiconductor conductivity is σ = qnµn + qpµp and therefore depends on the bound electron and hole concentrations and mobilities.

Candidate-only draft; authorized Admin review is absent.
