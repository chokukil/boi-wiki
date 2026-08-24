---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/science-ontology-binding
title: "Foundation ontology binding: measurement-uncertainty"
description: "Interpretation-only agent draft pending authorized Admin review"
tags:
  - ScienceVerifier
  - ScienceFoundation
  - Draft
timestamp: "2026-08-25T14:00:00+09:00"
boi_id: "boi:public:science:ontology-binding:common:measurement-uncertainty"
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
    ref: sci-evidence:common:uncertainty-error
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  binding_id: "sci:binding:common:measurement-uncertainty"
  ontology_release_id: "sci:ontology:science-foundation-draft/0.1.0"
  concept_id: "sci:concept:measurement-uncertainty"
  aliases:
    - "measurement uncertainty"
    - "측정 불확도"
    - "불확도"
  meaning: "The metrology concept identified as measurement uncertainty in a resolved vocabulary context."
  domain: general-science
  must_not_collapse:
    - "sci:concept:measurement-error"
  interpretation_only: true
  relation_provenance: declared_agent_draft
  release_eligibility: blocked_pending_authorized_admin_review
---

# measurement-uncertainty

This binding helps interpret Korean and English terms. It cannot supply a scientific outcome, relation direction, or verdict.
