---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/science-ontology-binding
title: "Foundation ontology binding: association"
description: "Interpretation-only agent draft pending authorized Admin review"
tags:
  - ScienceVerifier
  - ScienceFoundation
  - Draft
timestamp: "2026-08-25T14:00:00+09:00"
boi_id: "boi:public:science:ontology-binding:common:association"
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
  binding_id: "sci:binding:common:association"
  ontology_release_id: "sci:ontology:general-science-draft/0.1.0"
  concept_id: "sci:concept:association"
  aliases:
    - "association"
    - "statistical association"
    - "연관"
    - "연관성"
  meaning: "A broad observed statistical dependence that is not silently treated as quantified correlation or causation."
  domain: general-science
  must_not_collapse:
    - "sci:concept:correlation"
    - "sci:concept:causation"
  interpretation_only: true
  relation_provenance: declared_agent_draft
  release_eligibility: blocked_pending_authorized_admin_review
---

# association

This binding keeps broad association language distinct from quantified correlation and causation. It cannot supply a scientific outcome, relation direction, or verdict.
