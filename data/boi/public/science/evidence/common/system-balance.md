---
okf_version: '0.1'
boi_profile_version: '0.1'
sci_profile_version: '0.1'
type: boi/science-evidence
title: 'common: system-balance'
description: Short agent-curated, locator-bound Science Verifier evidence draft
tags:
- ScienceVerifier
- ScienceEvidence
- common
timestamp: '2026-08-25T03:20:00+09:00'
boi_id: boi:public:science:evidence:common:system-balance
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
  evidence_id: sci-evidence:common:system-balance
  source_id: sci-source:mit-2-25
  locator:
    medium: pdf
    resource_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/d11fcb4ad68d875ce88a12c18c263932_MIT2_25F13_Fundam_Law-Son.pdf
    content_hash: sha256:1fdf4743cd6f8ba3718bdc6029ef7f2721d0a5f1e506c3f86ad78578f5780b31
    section: 1.2 Laws for a Material Particle
    retrieved_at: '2026-08-25T02:45:00+09:00'
    exact: true
    requested_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/d11fcb4ad68d875ce88a12c18c263932_MIT2_25F13_Fundam_Law-Son.pdf
    resolved_url: https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/d11fcb4ad68d875ce88a12c18c263932_MIT2_25F13_Fundam_Law-Son.pdf
    preservation_status: checksum_only_no_archived_copy
    pdf_page_index: 3
    printed_page: printed/PDF page 4
    hash_scope: retrieved_pdf_bytes
  original_text: This law asserts that the mass δM = ρδV of a material particle remains invariant.
  original_text_hash: sha256:1515730ab01f2123dd8d50ed5755e0f3611c0cd61194ab11f47b8e821262a55f
  language: en
  reviewed_translation: 이 법칙은 물질 입자의 질량 δM = ρδV가 변하지 않음을 말한다.
  decision_eligibility: pending_review
  access_limitation: ''
  contextual_limitations:
  - This material-particle statement must be transformed carefully before applying it to an open control volume.
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
