---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SPN-004 Product-scoped spin-speed direction",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:spin-coating:004",
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
    "rule_id": "sci-rule:spin-coating:004",
    "standard_id": "R-SPN-004",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:spin-speed",
      "sci:concept:film-thickness"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:spin-speed",
    "object_concept_id": "sci:concept:film-thickness",
    "relation_kind": "monotonic_direction",
    "required_conditions": [
      {
        "key": "product_family",
        "operator": "eq",
        "value": "AZ 125nXT"
      },
      {
        "key": "product_grade",
        "operator": "in",
        "values": [
          "AZ 125nXT-10 B",
          "AZ 125nXT-7 B"
        ]
      },
      {
        "key": "source_revision",
        "operator": "eq",
        "value": "01/24"
      },
      {
        "key": "spin_speed_rpm",
        "operator": "range",
        "range": {
          "minimum": 600,
          "maximum": 2300
        },
        "unit": "rpm"
      },
      {
        "key": "evidence_use_mode",
        "operator": "eq",
        "value": "plotted_markers_only"
      },
      {
        "key": "material_class",
        "operator": "eq",
        "value": "photoresist"
      },
      {
        "key": "process_method",
        "operator": "eq",
        "value": "spin_coating"
      },
      {
        "key": "thinning_continues_until",
        "operator": "eq",
        "value": "drying_stops_flow"
      },
      {
        "key": "resist_identity",
        "operator": "eq",
        "value": "same"
      },
      {
        "key": "viscosity",
        "operator": "eq",
        "value": "same"
      },
      {
        "key": "solids_fraction",
        "operator": "eq",
        "value": "same"
      },
      {
        "key": "spin_time",
        "operator": "eq",
        "value": "same"
      },
      {
        "key": "environment",
        "operator": "eq",
        "value": "same"
      },
      {
        "key": "measurement_state",
        "operator": "eq",
        "value": "dry_post_bake"
      },
      {
        "key": "process_stage",
        "operator": "eq",
        "value": "final_coat_spin"
      }
    ],
    "validity_conditions": [
      {
        "key": "comparison_domain",
        "operator": "eq",
        "value": "inside_bound_product_curve"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "claim_specificity",
        "operator": "eq",
        "value": "equipment_or_numeric"
      }
    ],
    "context_dimensions": {
      "spin_rate": "rpm"
    },
    "knowledge_refs": [
      "sci:spin-coating:004"
    ],
    "evidence_refs": [
      "sci-evidence:spin-coating:vendor-spin-curve-observation",
      "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:spin-coating:vendor-spin-curve-observation",
        "claim_family": "spin_coating.rpm_thickness_direction.product_scoped_figure_observation",
        "purpose": "Both plotted AZ 125nXT grades show decreasing thickness as spin speed increases across their displayed markers."
      },
      {
        "evidence_ref": "sci-evidence:spin-coating:microchemicals-spin-speed-direction",
        "claim_family": "spin_coating.spin_speed_thickness_direction.drying_limited_process",
        "purpose": "For a drying-limited photoresist spin-coating process, attainable film thickness decreases approximately with the reciprocal square root of spin speed."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "decreases",
    "contradiction_predicates": [
      "increases"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-SPN-004 — Product-scoped spin-speed direction

Closed evaluator: `directional_relation`. Candidate qualification only.
