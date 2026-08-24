---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/science-ontology-binding
title: "Foundation ontology binding: model"
description: "Interpretation-only agent draft pending authorized Admin review"
tags:
  - ScienceVerifier
  - ScienceFoundation
  - Draft
timestamp: "2026-08-25T14:00:00+09:00"
boi_id: "boi:public:science:ontology-binding:common:model"
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
    ref: sci-evidence:common:model-validity
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  binding_id: "sci:binding:common:model"
  ontology_release_id: "sci:ontology:science-foundation-draft/0.1.0"
  concept_id: "sci:concept:model"
  aliases:
    - "model"
    - "scientific model"
    - "모델"
    - "과학 모델"
  meaning: "A specified representation used for a stated scientific purpose and domain."
  domain: general-science
  must_not_collapse:
    - "sci:concept:observation"
    - "sci:concept:theory"
  interpretation_only: true
  relation_provenance: declared_agent_draft
  release_eligibility: blocked_pending_authorized_admin_review
---

# model

This binding helps interpret Korean and English terms. It cannot supply a scientific outcome, relation direction, or verdict.
