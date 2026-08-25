---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-CIR-002 Kirchhoff voltage law",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:circuits:002",
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
      "ref": "sci-evidence:circuits:kvl-law"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:circuits:002",
    "domain_topic_id": "SCI-CIR-002",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "knowledge_kind": "model",
    "assurance_basis": "derived_model",
    "statement": "For a lumped circuit loop with consistent polarity and traversal conventions, the algebraic sum of loop voltages is zero.",
    "assumptions": [
      "All Rule conditions for sci-rule:circuits:002 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:circuits:002."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:circuits:kvl-law"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:circuits:kvl-law",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equations": [
      {
        "equation_id": "sci:equation:circuits:kvl-loop-balance",
        "scientific_role": "law",
        "decision_use": "deterministic_rule",
        "semantic_expression": {
          "schema_version": "science-expression/0.1",
          "root": {
            "op": "relation",
            "left": {
              "op": "variable",
              "variable_id": "algebraic_voltage_sum"
            },
            "right": {
              "op": "variable",
              "variable_id": "zero_voltage"
            },
            "relation": "eq"
          }
        },
        "display_latex": "\\sum_{k} V_k = 0",
        "plain_text": "sum(loop voltages with sign) = 0 V",
        "accessibility_reading": "The algebraic sum of voltages around the loop equals zero.",
        "variables": [
          {
            "variable_id": "algebraic_voltage_sum",
            "symbol": "ΣV_loop",
            "concept_ref": "sci:concept:loop-voltage-sum",
            "quantity_kind": "algebraic_voltage_sum",
            "dimension": {
              "mass": 1,
              "length": 2,
              "time": -3,
              "electric_current": -1
            },
            "unit": "volt",
            "definition": "Algebraic voltage sum around the bound loop.",
            "domain": "real",
            "sign_constraint": "any"
          },
          {
            "variable_id": "zero_voltage",
            "symbol": "0 V",
            "concept_ref": "sci:concept:zero-voltage",
            "quantity_kind": "zero_voltage",
            "dimension": {
              "mass": 1,
              "length": 2,
              "time": -3,
              "electric_current": -1
            },
            "unit": "volt",
            "definition": "Zero potential difference used as the equality reference.",
            "domain": "real",
            "sign_constraint": "any"
          }
        ],
        "assumptions": [
          "Voltage polarities and loop traversal direction are assigned consistently."
        ],
        "applicability": [
          "A bound closed path in the stated lumped-circuit context."
        ],
        "invalid_outside": [
          "Inconsistent polarity/traversal assignments or unqualified non-lumped electromagnetic cases."
        ],
        "boundary_conditions": [
          {
            "condition_id": "zero-reference",
            "statement": "The equality reference is zero volts.",
            "variable_id": "zero_voltage",
            "operator": "eq",
            "value": "0",
            "unit": "volt"
          }
        ],
        "approximation": null,
        "empirical_fit": null,
        "original_notation_mapping": [
          {
            "source_symbol": "voltages in the loop",
            "variable_id": "algebraic_voltage_sum"
          },
          {
            "source_symbol": "zero",
            "variable_id": "zero_voltage"
          }
        ],
        "evidence_uses": [
          {
            "evidence_ref": "sci-evidence:circuits:kvl-law",
            "purpose": "Bind the loop-voltage equality and its polarity/traversal convention.",
            "claim_scope_hash": "sha256:35425feac574fe96bee64893f714ce69ebe4e6bd265741ad55600e0d0e4cb268",
            "locator": {
              "medium": "pdf",
              "resource_url": "https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/c7c33e6a7c168cda50ff54f99c45e041_6_0022007L02.pdf",
              "content_hash": "sha256:b4c453cd2265ef5a94a2a2ce4025078a870b4db9c6d70a2bf3aa7722ecc8fba8",
              "exact": true,
              "section": "Transcript — Lecture 2, Kirchhoff laws",
              "pdf_page_index": 2,
              "printed_page": "PDF page 3",
              "equation_label": "KVL definition sentence (prose)"
            },
            "locator_digest": "sha256:60d2afffd160c4a7a9c035c158e41c70efca3b3ded9709275a7d1a0918c1ddd2",
            "transcription": {
              "transcription_id": "sci:transcription:circuits:kvl-loop-balance",
              "original_notation": "KVL simply states that if I have some circuit, and if I measured the voltages in any loop in the circuit, so if I look at the voltages in any loop, then the voltages in the loop would sum to zero.",
              "original_notation_hash": "sha256:3df590628532e97bddec3adead00371adabc5112b4e06e0a8bfe0260fcbe1032",
              "variable_context": [
                {
                  "source_symbol": "voltages in the loop",
                  "definition": "Algebraic voltage sum around the bound loop.",
                  "unit_text": "volt"
                },
                {
                  "source_symbol": "zero",
                  "definition": "Zero potential difference used as the equality reference.",
                  "unit_text": "volt"
                }
              ],
              "variable_context_hash": "sha256:011fbead6b2b2c64ef012467394bf78490e8c174ef7c5b12611539aea3199d3b",
              "coordinate_convention": "One traversal direction is fixed around the bound closed loop.",
              "sign_convention": "Each voltage sign follows its polarity relative to that traversal direction.",
              "unit_convention": "Every loop term and the zero reference use volts.",
              "conventions_hash": "sha256:ac9449e3ed1448440d29cfc6a6a3ac3ca547249edce540ac3e7747327bc6c2f2",
              "relation_notation": "equals",
              "transcription_method": "manual",
              "review_state": "reviewed",
              "reviewer": "agent:codex-transcription-draft",
              "reviewed_at": "2026-08-25T11:00:00+09:00",
              "semantic_expression_digest": "sha256:b6c53802a62692b96cdd764ee3c365149a5d7d14b3d5b7179e5fb9b82bff0ae5",
              "transcription_digest": "sha256:eefc0248c06ea37acc53cc274f80b6eacbd22595db1ac60421a0a1eb2fa07c2d"
            }
          }
        ],
        "evaluator": {
          "evaluator_id": "sci-evaluator:closed-arithmetic-relation",
          "version": "0.1.0",
          "expression_schema_version": "science-expression/0.1",
          "allowed_operators": [
            "relation",
            "variable"
          ],
          "evaluator_digest": "sha256:a2324dddd46cd907539eb675d129edfcee646af75b94763f54a365d54c1276ac"
        },
        "equation_digest": "sha256:ae4be4aacf85dde9c31fd93a090f0a378aeeb3470c115ca95a8a30165e8147ef"
      }
    ]
  }
}
---

# SCI-CIR-002 — Kirchhoff voltage law

For a lumped circuit loop with consistent polarity and traversal conventions, the algebraic sum of loop voltages is zero.

Candidate-only draft; authorized Admin review is absent.
