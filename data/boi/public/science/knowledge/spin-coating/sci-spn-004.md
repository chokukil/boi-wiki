---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-SPN-004 Drying-limited spin-speed direction",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:spin-coating:004",
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
      "ref": "sci-evidence:spin-coating:vendor-spin-curve-observation"
    },
    {
      "type": "boi",
      "ref": "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:spin-coating:004",
    "domain_topic_id": "SCI-SPN-004",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "knowledge_kind": "conditional_relation",
    "assurance_basis": "derived_model",
    "statement": "When photoresist spin-off continues until drying stops the flow, attainable resist film thickness decreases approximately with the reciprocal square root of spin speed.",
    "assumptions": [
      "All Rule conditions for sci-rule:spin-coating:004 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:spin-coating:004."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:spin-coating:vendor-spin-curve-observation",
      "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:spin-coating:vendor-spin-curve-observation",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      },
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equations": [
      {
        "equation_id": "sci:equation:spin-coating:drying-limited-power-law",
        "scientific_role": "approximation",
        "decision_use": "explanation_only",
        "semantic_expression": {
          "schema_version": "science-expression/0.1",
          "root": {
            "op": "relation",
            "left": {
              "op": "variable",
              "variable_id": "film_thickness"
            },
            "right": {
              "op": "power",
              "left": {
                "op": "variable",
                "variable_id": "spin_speed"
              },
              "right": {
                "op": "literal",
                "value": "-0.5"
              }
            },
            "relation": "proportional"
          }
        },
        "display_latex": "h \\propto \\omega^{-1/2}",
        "plain_text": "h proportional to omega^(-1/2)",
        "accessibility_reading": "Film thickness is approximately proportional to the reciprocal square root of spin speed.",
        "variables": [
          {
            "variable_id": "film_thickness",
            "symbol": "h",
            "concept_ref": "sci:concept:film-thickness",
            "quantity_kind": "film_thickness",
            "dimension": {
              "length": 1
            },
            "unit": "meter",
            "definition": "Attainable dried photoresist film thickness.",
            "domain": "real",
            "sign_constraint": "positive"
          },
          {
            "variable_id": "spin_speed",
            "symbol": "ω",
            "concept_ref": "sci:concept:spin-speed",
            "quantity_kind": "spin_speed",
            "dimension": {
              "time": -1
            },
            "unit": "1 / second",
            "definition": "Attained final spin speed in the cited drying-limited process.",
            "domain": "real",
            "sign_constraint": "positive"
          }
        ],
        "assumptions": [
          "Photoresist spin-off continues until drying stops the flow."
        ],
        "applicability": [
          "Direction and approximate power-law form for the cited drying-limited photoresist process."
        ],
        "invalid_outside": [
          "Numeric recipe transfer, changed material/equipment conditions, or extrapolation beyond a qualified process domain."
        ],
        "boundary_conditions": [
          {
            "condition_id": "positive-spin-speed",
            "statement": "Spin speed must be positive.",
            "variable_id": "spin_speed",
            "operator": "gt",
            "value": "0",
            "unit": "1 / second"
          }
        ],
        "approximation": {
          "approximation_kind": "continuum_model",
          "error_statement": "The source states a good approximation but supplies no universal numeric error bound; magnitude requires process-specific qualification.",
          "validity_conditions": [
            "Spin-off continues until drying stops the flow."
          ]
        },
        "empirical_fit": null,
        "original_notation_mapping": [
          {
            "source_symbol": "attainable resist film thickness",
            "variable_id": "film_thickness"
          },
          {
            "source_symbol": "spin speed",
            "variable_id": "spin_speed"
          }
        ],
        "evidence_uses": [
          {
            "evidence_ref": "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
            "purpose": "Bind the stated reciprocal-square-root approximation and its drying-limited conditions without authorizing a recipe.",
            "claim_scope_hash": "sha256:b9e788573d5bb37a51a131c93947bdb0701ba98a1fe54c8e4415a273fb2fa4a2",
            "locator": {
              "medium": "pdf",
              "resource_url": "https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf",
              "content_hash": "sha256:3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7",
              "exact": true,
              "section": "Influence of the Attained Spin Speed",
              "pdf_page_index": 0,
              "printed_page": "PDF page 1",
              "equation_label": "Influence of the Attained Spin Speed (prose power law)"
            },
            "locator_digest": "sha256:ba98c256ba42e0a95016036362e78553f0745d45246307c85412cd4f4c202a1a",
            "transcription": {
              "transcription_id": "sci:transcription:spin-coating:drying-limited-power-law",
              "original_notation": "If, as usual, the spin-coating of the resist from the substrate continues until it has been stopped by the drying process, the attainable resist film thickness decreases in a good approximation with the reciprocal square root of the spin speed (Fig. 54).",
              "original_notation_hash": "sha256:40b4fe4a8c1931dc6fc235fdb77a170a111504c8eca41566186953d6d5687d27",
              "variable_context": [
                {
                  "source_symbol": "attainable resist film thickness",
                  "definition": "Attainable dried photoresist film thickness.",
                  "unit_text": "meter"
                },
                {
                  "source_symbol": "spin speed",
                  "definition": "Attained final spin speed in the cited drying-limited process.",
                  "unit_text": "1 / second"
                }
              ],
              "variable_context_hash": "sha256:842302a78f1f25e1c496b2622c0f4e5f7364077dcccc3d23a3fb199309c82c03",
              "coordinate_convention": "Thickness is normal to the substrate; spin speed is the attained rotational-rate magnitude.",
              "sign_convention": "Film thickness and spin-speed magnitude are positive.",
              "unit_convention": "Only the proportional direction and exponent are retained; no universal proportionality constant is asserted.",
              "conventions_hash": "sha256:685299260bf899c367bd1328fa9cda4df9fd4e370a9041d4d49ea29fc54f09cb",
              "relation_notation": "proportionality",
              "transcription_method": "manual",
              "review_state": "reviewed",
              "reviewer": "agent:codex-transcription-draft",
              "reviewed_at": "2026-08-25T11:00:00+09:00",
              "semantic_expression_digest": "sha256:48d32d9b855a493a13433c8090025db59cf25f03a22fb5d3f51b56e7210a25e2",
              "transcription_digest": "sha256:f6e65ff5ca3040211abd4cc1370e2753f283704553b6dfd5d92a7a2d75acf2d4"
            }
          }
        ],
        "evaluator": null,
        "equation_digest": "sha256:4d478fd6bf071a065d61974b648f2124c1ae1f2425c0da53be0233ccc3513470"
      }
    ]
  }
}
---

# SCI-SPN-004 Drying-limited spin-speed direction

When photoresist spin-off continues until drying stops the flow, attainable resist film thickness decreases approximately with the reciprocal square root of spin speed.

Candidate-only draft; authorized Admin review is absent.
