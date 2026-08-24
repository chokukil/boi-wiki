---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/science-ontology-binding
title: "Common ontology binding: increases"
description: "Interpretation-only increasing-direction language pending authorized Admin review"
tags:
  - ScienceVerifier
  - ScienceFoundation
  - Draft
timestamp: "2026-08-25T18:05:00+09:00"
boi_id: boi:public:science:ontology-binding:common:increases
visibility: public
classification: internal
owner: science-admin
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
  - type: boi
    ref: sci-evidence:common:correlation-causation
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  binding_id: "sci:binding:common:increases"
  ontology_release_id: "sci:ontology:general-science-draft/0.1.0"
  concept_id: "increases"
  aliases:
    - "increase"
    - "increases"
    - "increased"
    - "higher"
    - "증가"
    - "증가한다"
    - "높이면"
    - "높이려면"
    - "높여야 한다"
    - "높아진다"
    - "올리면"
  meaning: "The input wording asserts an increasing direction. It supplies no causal relation, scientific law, expected outcome, or verdict."
  domain: general-science
  must_not_collapse:
    - "sci:concept:association"
    - "sci:concept:causation"
  interpretation_only: true
  relation_provenance: declared_agent_draft
  decision_impact: interpretation_candidate_only_no_outcome_authority
  release_eligibility: blocked_pending_authorized_admin_review
---

# increases

This binding preserves an increasing direction asserted by the input. Only an
authorized released Rule may decide whether that direction is scientifically
consistent or contradictory.
