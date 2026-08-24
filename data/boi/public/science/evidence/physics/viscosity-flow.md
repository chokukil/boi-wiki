---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'physics: viscosity-flow'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- physics
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:physics:viscosity-flow
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
  ref: boi:public:science:source:mit-2-25
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
science:
  evidence_id: sci-evidence:physics:viscosity-flow
  source_id: sci-source:mit-2-25
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/83aa0d8fd395e8e7d9bc8b236ab4bfe7_MIT2_25F13_Equat_of_Motio.pdf
    content_hash: sha256:ede6b8dcb71a7d2965f87ae9419749f1b2f8994e89ea0d92c438c71a9af037cf
    section: 5. Simple Fluids
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/83aa0d8fd395e8e7d9bc8b236ab4bfe7_MIT2_25F13_Equat_of_Motio.pdf
    resolved_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/83aa0d8fd395e8e7d9bc8b236ab4bfe7_MIT2_25F13_Equat_of_Motio.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 12
    printed_page: printed/PDF page 13
    hash_scope: retrieved_pdf_bytes
  original_text: The defining attribute of a simple fluid, however, is that it keeps deforming, or straining, as long as any
    shear stress, no matter how small, is applied to it.
  original_text_hash: sha256:14050b6414fe334508cef8b37c343c3447066254b7566f28e2faebe68c2f7235
  language: en
  reviewed_translation: 단순 유체는 아무리 작은 전단응력이라도 작용하는 동안 계속 변형된다는 특성을 갖는다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This is not a Newtonian constitutive equation and does not supply a viscosity value.
  supports_knowledge: []
  curation_actor:
    type: agent
    agent_id: codex
  curated_at: '2026-08-25T03:26:00+09:00'
  release_eligibility: blocked_pending_authorized_admin_review
  translation:
    status: agent_draft_pending_admin_review
    permission_status: not_assessed
    original_controls: true
    actor:
      type: agent
      agent_id: codex
---

# Review scope

This agent-curated draft stores one minimal locator-bound span. It cannot enter an active verdict path until an authorized Admin review event is recorded. Any later use remains limited by the locator, source version, allowed-claim scope, and contextual limitations.
