---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-knowledge",
  "title": "SCI-PHY-003 Work and kinetic-energy change",
  "description": "Atomic domain Knowledge draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:knowledge:physics:003",
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
      "ref": "sci-evidence:physics:work-energy-power"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "knowledge_id": "sci:physics:003",
    "domain_topic_id": "SCI-PHY-003",
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "knowledge_kind": "model",
    "assurance_basis": "derived_model",
    "statement": "The net work done by the applied force equals the object's change in kinetic energy within the work-kinetic-energy theorem's scope.",
    "assumptions": [
      "All Rule conditions for sci-rule:physics:003 are checked before any decision."
    ],
    "applicability": {
      "scope": "Only the typed validity domain of sci-rule:physics:003."
    },
    "limitations": [
      "This AI-authored draft cannot enter an active decision path before authorized Admin review."
    ],
    "invalid_outside": [
      "claims missing a required condition or outside a typed validity constraint"
    ],
    "related_knowledge": [],
    "evidence_refs": [
      "sci-evidence:physics:work-energy-power"
    ],
    "evidence_roles": [
      {
        "evidence_ref": "sci-evidence:physics:work-energy-power",
        "role": "locator_bound_support",
        "scope_note": "Use only the Evidence object's embedded claim scope."
      }
    ],
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equations": [
      {
        "equation_id": "sci:equation:physics:applied-work-kinetic-energy-change",
        "scientific_role": "law",
        "decision_use": "deterministic_rule",
        "semantic_expression": {
          "schema_version": "science-expression/0.1",
          "root": {
            "op": "relation",
            "left": {
              "op": "variable",
              "variable_id": "applied_work"
            },
            "right": {
              "op": "variable",
              "variable_id": "kinetic_energy_change"
            },
            "relation": "eq"
          }
        },
        "display_latex": "W_{\\mathrm{applied}} = \\Delta K",
        "plain_text": "W_applied = delta_K",
        "accessibility_reading": "Applied-force work equals the change in kinetic energy.",
        "variables": [
          {
            "variable_id": "applied_work",
            "symbol": "W_applied",
            "concept_ref": "sci:concept:applied-force-work",
            "quantity_kind": "applied_work",
            "dimension": {
              "mass": 1,
              "length": 2,
              "time": -2
            },
            "unit": "joule",
            "definition": "Work done by the applied force on the bounded object.",
            "domain": "real",
            "sign_constraint": "any"
          },
          {
            "variable_id": "kinetic_energy_change",
            "symbol": "ΔK",
            "concept_ref": "sci:concept:kinetic-energy-change",
            "quantity_kind": "kinetic_energy_change",
            "dimension": {
              "mass": 1,
              "length": 2,
              "time": -2
            },
            "unit": "joule",
            "definition": "Change in the object's kinetic energy.",
            "domain": "real",
            "sign_constraint": "any"
          }
        ],
        "assumptions": [
          "The object boundary and all applied-force work terms are explicit."
        ],
        "applicability": [
          "Work-kinetic-energy theorem for the stated bounded object."
        ],
        "invalid_outside": [
          "Incomplete work accounting or an unspecified object system."
        ],
        "boundary_conditions": [],
        "approximation": null,
        "empirical_fit": null,
        "original_notation_mapping": [
          {
            "source_symbol": "work done by the applied force",
            "variable_id": "applied_work"
          },
          {
            "source_symbol": "change in kinetic energy",
            "variable_id": "kinetic_energy_change"
          }
        ],
        "evidence_uses": [
          {
            "evidence_ref": "sci-evidence:physics:work-energy-power",
            "purpose": "Bind the exact work-kinetic-energy equality and its object scope.",
            "claim_scope_hash": "sha256:b0ad6297d6084cc3943e15f50e4832ef1bf2bbd0d587067ee5d8c3327e71dce7",
            "locator": {
              "medium": "pdf",
              "resource_url": "https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/mit8_01scs22_chapter13.pdf",
              "content_hash": "sha256:a6bf0626b4c9446a7b6aec206024b90f611403eb059a8dd7ffc45fe1a98fec00",
              "exact": true,
              "section": "13.6 Work-Kinetic Energy Theorem",
              "pdf_page_index": 16,
              "printed_page": "printed 13-16; PDF page 17",
              "equation_label": "Section 13.6 theorem statement (prose)"
            },
            "locator_digest": "sha256:529873a3ab7fa12723d80ff90208971283771a666d5f0b62fa252a4b6f9861b9",
            "transcription": {
              "transcription_id": "sci:transcription:physics:applied-work-kinetic-energy-change",
              "original_notation": "the work done by the applied force on an object is identically equal to the change in kinetic energy of the object.",
              "original_notation_hash": "sha256:a89023544a44dc493b7d3bd17bf459fd113b891c82e1051049cee3b60a44d361",
              "variable_context": [
                {
                  "source_symbol": "work done by the applied force",
                  "definition": "Work done by the applied force on the bounded object.",
                  "unit_text": "joule"
                },
                {
                  "source_symbol": "change in kinetic energy",
                  "definition": "Change in the object's kinetic energy.",
                  "unit_text": "joule"
                }
              ],
              "variable_context_hash": "sha256:840eeee63309c3d0791c31082b0ef2fe875b6ef0e7af87907a7ac95a5b0da591",
              "coordinate_convention": "Work and kinetic-energy change use the same bounded object and interval.",
              "sign_convention": "Positive work increases kinetic energy under the cited theorem statement.",
              "unit_convention": "Both energy quantities use coherent SI joules.",
              "conventions_hash": "sha256:79a92be04be1a4b0e21437789a5e9d11fc96aeb515bda8394970e2ba6cacc087",
              "relation_notation": "equals",
              "transcription_method": "manual",
              "review_state": "reviewed",
              "reviewer": "agent:codex-transcription-draft",
              "reviewed_at": "2026-08-25T11:00:00+09:00",
              "semantic_expression_digest": "sha256:75e17e0636a443eeb759dced56fb63e3fabeb691390937d08c19b1e4e4199167",
              "transcription_digest": "sha256:b2c1bbf0f1ab484abc024286a56000381ea0fe1a304889dc29822dd3cf8bbd08"
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
        "equation_digest": "sha256:09ee2b7f81aa3fddd1f45e7ceb636053c7fc0f6a1b10cd57978a597e9d013bf5"
      }
    ]
  }
}
---

# SCI-PHY-003 — Work and kinetic-energy change

The net work done by the applied force equals the object's change in kinetic energy within the work-kinetic-energy theorem's scope.

Candidate-only draft; authorized Admin review is absent.
